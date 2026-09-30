import json
import re
import subprocess
import sys
import threading
import time
import uuid
from urllib.parse import urlsplit

from .config import ROOT, cookie_args, yt_args, ffmpeg_available
from .security import validate_url, friendly_error

INSPECTIONS: dict = {}
LOCK = threading.Lock()
IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'avif'}
AUDIO_EXTS = {'m4a', 'mp3', 'opus', 'ogg', 'oga', 'aac', 'flac', 'wav', 'weba'}
# Extractors whose "playlists" are one post holding several videos/photos, not a channel.
POST_EXTRACTORS = {'X', 'Twitter', 'Instagram', 'Reddit', 'TikTok', 'Bluesky', 'Facebook', 'Tumblr', 'Imgur'}


class MediaError(ValueError):
    pass


def run_engine(module, args, timeout=90):
    # cwd=ROOT puts the project's yt_dlp_plugins package on sys.path.
    try:
        result = subprocess.run([sys.executable, '-m', module, *args], capture_output=True, cwd=ROOT,
                                text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise MediaError('The source took too long to respond. Try a single post or video link.') from exc
    if result.returncode:
        raise MediaError(friendly_error(result.stderr))
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise MediaError('The source returned no usable media.') from exc


def is_video(f):
    # yt-dlp uses 'none' for an absent stream and None for "unknown" (common on HLS streams).
    if f.get('vcodec') == 'none':
        return False
    return not (f.get('vcodec') is None and not f.get('height') and f.get('ext') in AUDIO_EXTS)


def is_audio_only(f):
    return not is_video(f) and f.get('acodec') != 'none'


def bitrate(f):
    # HLS audio renditions often only carry their bitrate in the id (e.g. "hls-audio-128000-Audio").
    found = re.search(r'audio-(\d{4,})', str(f.get('format_id')))
    return f.get('abr') or f.get('tbr') or (int(found.group(1)) / 1000 if found else 0)


def mp4_audio(f):
    return f.get('ext') in ('m4a', 'mp4')


def rank(f):
    # Site-declared quality, then direct files over segmented streams, then bitrate.
    direct = str(f.get('protocol') or 'https') in ('http', 'https')
    return (f.get('quality') or 0, direct, f.get('tbr') or 0, f.get('filesize') or f.get('filesize_approx') or 0)


def video_options(info):
    formats = [f for f in info.get('formats', []) if not f.get('has_drm') and f.get('format_id')
               and re.fullmatch(r'[\w.-]+', str(f['format_id'])) and f.get('ext') not in ('mhtml', *IMAGE_EXTS)
               and 'storyboard' not in str(f.get('format_note') or '')]
    audio = [f for f in formats if is_audio_only(f)]
    has_ffmpeg = ffmpeg_available()
    best_audio = max(audio, key=bitrate, default=None)
    best = {}
    for f in formats:
        if not is_video(f):
            continue
        silent = f.get('acodec') == 'none'
        companion = best_audio
        # Matching MP4/M4A or WebM/Opus preserves source codecs; MKV handles mixed containers.
        compatible = [a for a in audio if (mp4_audio(a) if f.get('ext') == 'mp4' else a.get('ext') == 'webm')]
        if compatible:
            companion = max(compatible, key=bitrate)
        merge = silent and companion is not None and has_ffmpeg
        selector = str(f['format_id']) + ('+' + str(companion['format_id']) if merge else '')
        ext = f.get('ext') or 'mp4'
        if merge and not ((ext == 'mp4' and mp4_audio(companion)) or (ext == 'webm' and companion.get('ext') == 'webm')):
            ext = 'mkv'
        size = f.get('filesize') or f.get('filesize_approx')
        if merge and size:
            extra = companion.get('filesize') or companion.get('filesize_approx')
            size = size + extra if extra else None
        height = f.get('height')
        fps = round(f['fps']) if f.get('fps') else None
        has_audio = not silent or merge
        note = str(f.get('format_note') or '')
        if re.fullmatch(r'(?i)\d+p\d*|hls|dash( video)?|low|high|', note):
            note = ''
        if silent and companion and not has_ffmpeg:
            note = 'Video only · install FFmpeg to add audio'
        elif silent and not merge:
            note = 'Video only'
        option = {'id': 'v-' + str(f['format_id']), 'kind': 'video',
                  'label': f'{height}p' if height else str(f.get('format_note') or f['format_id']).capitalize() + ' quality',
                  'ext': ext, 'height': height or 0, 'fps': fps, 'size': size,
                  'codec': str(f.get('vcodec') or '').split('.')[0], 'audio': has_audio,
                  'note': note, 'selector': selector, '_rank': rank(f)}
        # Sites often publish the same rendition twice (direct file + HLS); keep the better one.
        key = (option['height'] or option['label'], (fps or 0) > 30, ext, has_audio)
        if key not in best or option['_rank'] > best[key]['_rank']:
            best[key] = option
    options = sorted(best.values(), key=lambda o: (o['height'], o.get('fps') or 0, o['audio'], o['_rank']), reverse=True)
    for option in options:
        del option['_rank']
    seen_audio = set()
    # Non-DRC tracks sort first so loudness-compressed duplicates are dropped.
    for f in sorted(audio, key=lambda a: (bitrate(a), '-drc' not in str(a['format_id'])), reverse=True):
        label = f'{round(bitrate(f))} kbps' if bitrate(f) else 'Original audio'
        if (label, f.get('ext')) in seen_audio:
            continue
        seen_audio.add((label, f.get('ext')))
        options.append({'id': 'a-' + str(f['format_id']), 'kind': 'audio', 'label': label,
                        'ext': f.get('ext', 'm4a'), 'height': 0, 'fps': None, 'size': f.get('filesize') or f.get('filesize_approx'),
                        'codec': f.get('acodec'), 'audio': True, 'note': '', 'selector': str(f['format_id'])})
    if has_ffmpeg and (audio or any(o['audio'] for o in options)):
        options.append({'id': 'mp3', 'kind': 'audio', 'label': 'MP3 · 320 kbps', 'ext': 'mp3', 'height': 0,
                        'fps': None, 'size': None, 'codec': 'mp3', 'audio': True, 'note': 'Converted from best available audio', 'selector': 'bestaudio/best'})
    return options


def image_options(info):
    images = [f for f in info.get('formats', []) if f.get('ext') in IMAGE_EXTS and f.get('format_id')
              and re.fullmatch(r'[\w.-]+', str(f['format_id']))]
    images.sort(key=lambda f: (f.get('width') or 0) * (f.get('height') or 0), reverse=True)
    return [{'id': 'i-' + str(f['format_id']), 'kind': 'image', 'ext': f['ext'], 'height': f.get('height') or 0,
             'label': f"{f['width']}×{f['height']}" if f.get('width') and f.get('height') else 'Original image',
             'fps': None, 'size': f.get('filesize'), 'codec': '', 'audio': False,
             'note': 'Original size' if f is images[0] else '', 'selector': str(f['format_id'])} for f in images]


def entry_options(info):
    return video_options(info) + image_options(info)


def post_options(entries):
    """One pick per item of a multi-media post, plus everything as a ZIP."""
    options = []
    for index, entry in enumerate(entries, 1):
        top = next((o for o in entry_options(entry) if o['kind'] != 'audio'), None)
        if not top:
            continue
        noun = 'Image' if top['kind'] == 'image' else 'Video'
        options.append({**top, 'id': f'item{index}-{top["id"]}', 'label': f'{noun} {index} · {top["label"]}',
                        'playlist_items': str(index)})
    if len(options) > 1:
        sizes = [o['size'] for o in options]
        options.insert(0, {'id': 'post-all', 'kind': 'video' if any(o['kind'] == 'video' for o in options) else 'image',
                           'label': f'All {len(options)} files · ZIP', 'ext': 'zip', 'height': 0, 'fps': None,
                           'size': sum(sizes) if all(sizes) else None, 'codec': '', 'audio': True,
                           'note': 'Best quality of each item', 'playlist_items': '1:50',
                           'selector': 'bv*+ba/b' if ffmpeg_available() else 'b/bv*'})
    return options


def inspect_media(url):
    url = validate_url(url)
    host = urlsplit(url).hostname or ''
    suffix = urlsplit(url).path.rsplit('.', 1)[-1].lower()
    result = None
    if suffix in IMAGE_EXTS:
        result = {'title': urlsplit(url).path.rsplit('/', 1)[-1], 'author': host, 'platform': host,
                  'duration': None, 'thumbnail': url, 'engine': 'direct', 'items': [{'url': url, 'ext': suffix}],
                  'options': [{'id': 'image-1', 'kind': 'image', 'label': 'Original image', 'ext': suffix, 'size': None, 'index': 1}]}
    else:
        try:
            info = run_engine('yt_dlp', [*yt_args(), '--dump-single-json', '--skip-download',
                                         '--playlist-items', '1:50', '--', url])
            entries = []
            if info.get('_type') in ('playlist', 'multi_video'):
                # Multi-media posts become a gallery; whole channels/playlists are out of scope.
                if info['_type'] != 'multi_video' and info.get('extractor_key') not in POST_EXTRACTORS:
                    raise MediaError('Paste a single video or post link. Playlists and channels are not supported.')
                entries = [e for e in info.get('entries') or [] if e and e.get('formats')]
                if len(entries) == 1:
                    info, entries = {**entries[0], 'title': entries[0].get('title') or info.get('title')}, []
            options = post_options(entries) if entries else entry_options(info)
            if not options:
                raise MediaError('No downloadable video formats were found.')
            first = entries[0] if entries else info
            result = {'title': info.get('title') or first.get('title') or 'Untitled video',
                      'author': info.get('uploader') or first.get('uploader') or info.get('channel') or host,
                      'platform': info.get('extractor_key') or host, 'duration': None if entries else info.get('duration'),
                      'thumbnail': info.get('thumbnail') or first.get('thumbnail'), 'engine': 'yt_dlp', 'options': options,
                      'items': [{} for _ in entries]}
        except MediaError as video_error:
            # Gallery extractors accept post URLs; cap extraction to keep profile links bounded.
            try:
                gallery = run_engine('gallery_dl', ['--config-ignore', '--no-input', '--range', '1-50',
                      '--http-timeout', '15', '--retries', '1', *cookie_args(), '--dump-json', '--', url])
                items = [{'url': row[1], 'ext': row[2].get('extension') or 'jpg', 'meta': row[2]}
                         for row in gallery if isinstance(row, list) and len(row) >= 3 and row[0] == 3]
                if not items:
                    raise video_error
                meta = items[0]['meta']
                options = [{'id': f'image-{i}', 'kind': 'image' if item['ext'] in IMAGE_EXTS else 'video',
                            'label': f"{'Image' if item['ext'] in IMAGE_EXTS else 'Video'} {i} · Original", 'ext': item['ext'],
                            'size': None, 'index': i, 'audio': True} for i, item in enumerate(items, 1)]
                if len(items) > 1:
                    options.insert(0, {'id': 'gallery-all', 'kind': 'image', 'label': f'All {len(items)} files · ZIP', 'ext': 'zip', 'size': None, 'index': None})
                result = {'title': str(meta.get('title') or meta.get('description') or meta.get('content') or 'Media post')[:180],
                          'author': str(meta.get('user', {}).get('name', host)) if isinstance(meta.get('user'), dict) else str(meta.get('author') or host),
                          'platform': str(meta.get('category') or host), 'duration': None, 'thumbnail': items[0]['url'] if items[0]['ext'] in IMAGE_EXTS else None,
                          'engine': 'gallery_dl', 'options': options, 'items': items}
            except MediaError:
                raise video_error
    inspection_id = uuid.uuid4().hex
    result.update({'id': inspection_id, 'url': url, 'created': time.time()})
    with LOCK:
        for key in list(INSPECTIONS):
            if INSPECTIONS[key]['created'] < time.time() - 3600:
                del INSPECTIONS[key]
        if len(INSPECTIONS) >= 100:
            del INSPECTIONS[next(iter(INSPECTIONS))]
        INSPECTIONS[inspection_id] = result
    return public_media(result)


def get_media(inspection_id):
    with LOCK:
        media = INSPECTIONS.get(inspection_id)
        if not media or media['created'] < time.time() - 3600:
            raise MediaError('This preview expired. Inspect the link again.')
        return media


def public_media(media):
    return {k: v for k, v in media.items() if k not in ('engine', 'items', 'thumbnail', 'created', 'options')} | {
        'thumbnail': f"/api/media/{media['id']}/thumbnail" if media.get('thumbnail') else None,
        'count': len(media['items']) or 1,
        'options': [{k: v for k, v in o.items() if k not in ('selector', 'index', 'playlist_items')} for o in media['options']]}
