"""One disposable process per download; stdout is a JSON progress protocol."""
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import yt_dlp

from .config import COOKIES, FFMPEG, cookie_args, ffmpeg_available
from .network import public_stream
from .security import friendly_error, validate_url

IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'avif'}
SKIP_SUFFIXES = ('.json', '.part', '.ytdl', '.tmp')


def emit(**event):
    print(json.dumps(event), flush=True)


class QuietLogger:
    def debug(self, _): pass
    def warning(self, _): pass
    def error(self, _): pass


def safe_name(value, fallback='media'):
    return re.sub(r'[^\w .()-]', '_', str(value or '')).strip(' .')[:100] or fallback


def produced_files(directory):
    return sorted(p for p in directory.rglob('*') if p.is_file() and p.suffix not in SKIP_SUFFIXES)


def ytdl_download(url, directory, title, selector, merge_format, on_progress, mp3=False, on_info=None, items='1:25'):
    def hook(data):
        if on_info and data.get('info_dict'):
            on_info(data['info_dict'])
        if data['status'] == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate')
            on_progress(data.get('downloaded_bytes', 0) / total if total else None, data.get('speed'), data.get('eta'))
        elif data['status'] == 'finished':
            on_progress(1, None, None)
    # Items of a multi-media post share a title, so they are told apart by their position.
    opts = {'format': selector, 'outtmpl': str(directory / (title + '%(playlist_index& - {}|)s.%(ext)s')),
            'noplaylist': True, 'playlist_items': items, 'quiet': True, 'no_warnings': True, 'logger': QuietLogger(),
            'socket_timeout': 20, 'retries': 2, 'fragment_retries': 3,
            'progress_hooks': [hook], 'merge_output_format': merge_format,
            'windowsfilenames': True, 'js_runtimes': {'node': {}}, 'cachedir': False}
    if COOKIES:
        opts['cookiefile'] = COOKIES
    if FFMPEG:
        opts['ffmpeg_location'] = FFMPEG
    if mp3:
        opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}]
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


def gallery_download(url, directory, selection='1-50', quiet=False):
    command = [sys.executable, '-m', 'gallery_dl', '--config-ignore', '--no-input', '--no-colors',
               '--no-postprocessors', '--http-timeout', '20', '--retries', '2',
               '--windows-filenames', '-D', str(directory), *cookie_args(), '--range', selection, '--', url]
    # In single mode stdout goes straight to the parent, which ignores non-protocol lines.
    subprocess.run(command, check=True, stderr=subprocess.STDOUT, stdout=subprocess.DEVNULL if quiet else None)


def direct_download(url, target, on_progress):
    with public_stream(url) as response:
        if not response.headers.get('content-type', '').startswith('image/'):
            raise ValueError('The link does not point to an image.')
        total = int(response.headers.get('content-length', 0))
        received = 0
        with target.open('wb') as file:
            for chunk in response.iter_bytes(128 * 1024):
                file.write(chunk)
                received += len(chunk)
                on_progress(received / total if total else None, None, None)


def download(spec):
    directory = Path(spec['directory'])
    directory.mkdir(parents=True, exist_ok=True)
    option = spec['option']
    title = safe_name(spec['title'])

    def progress(fraction, speed, eta):
        if fraction is not None and fraction >= 1:
            emit(status='processing', progress=95, speed=None, eta=None)
        else:
            emit(status='downloading', progress=min(94, fraction * 94) if fraction is not None else None, speed=speed, eta=eta)

    if spec['engine'] == 'yt_dlp':
        merge = option['ext'] if option['ext'] in ('mp4', 'mkv', 'webm', 'mov') else 'mp4/mkv'
        ytdl_download(spec['url'], directory, title, option['selector'], merge, progress,
                      mp3=option['id'] == 'mp3', items=option.get('playlist_items') or '1:25')
    elif spec['engine'] == 'gallery_dl':
        gallery_download(spec['url'], directory, str(option['index']) if option['index'] else '1-50')
    else:
        ext = option['ext']
        if not re.fullmatch(r'[a-z0-9]{1,8}', ext):
            raise ValueError('Invalid image format.')
        direct_download(spec['url'], directory / (title + '.' + ext), progress)
    files = produced_files(directory)
    if not files:
        raise ValueError('No file was produced by the source.')
    if option['id'] in ('gallery-all', 'post-all') or len(files) > 1:
        emit(status='processing', progress=97)
        archive = directory / (title + '.zip')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as zipper:
            for file in files:
                zipper.write(file, file.relative_to(directory))
        output = archive
    else:
        output = files[0]
    emit(status='completed', progress=100, filename=output.name, path=str(output), size=output.stat().st_size, speed=None, eta=None)


def fetch_best(url, directory, mode, progress, on_info):
    """Best-quality download of one batch link, trying each engine in turn."""
    validate_url(url)
    suffix = urlsplit(url).path.rsplit('.', 1)[-1].lower()
    if suffix in IMAGE_EXTS:
        name = safe_name(urlsplit(url).path.rsplit('/', 1)[-1].rsplit('.', 1)[0], 'image')
        on_info({'title': name})
        direct_download(url, directory / f'{name}.{suffix}', progress)
        return
    has_ffmpeg = ffmpeg_available()
    if mode == 'audio':
        selector, merge = 'ba/b', 'mp4/mkv'
    else:
        selector, merge = ('bv*+ba/b' if has_ffmpeg else 'b/bv*'), 'mp4/mkv'
    try:
        ytdl_download(url, directory, '%(title).90B [%(id)s]', selector, merge, progress,
                      mp3=mode == 'audio' and has_ffmpeg, on_info=on_info)
    except yt_dlp.utils.DownloadError as video_error:
        # Image posts (X, Instagram, Imgur, …) are gallery-dl territory.
        for leftover in directory.iterdir():
            if leftover.is_file():
                leftover.unlink()
        try:
            gallery_download(url, directory, quiet=True)
        except subprocess.CalledProcessError:
            raise video_error from None
    if not produced_files(directory):
        raise ValueError('No file was produced by the source.')


def batch(spec):
    directory = Path(spec['directory'])
    urls = spec['urls']
    mode = spec.get('mode', 'video')
    items = [{'url': url, 'status': 'queued', 'title': None, 'error': None} for url in urls]
    total = len(urls)
    archive = directory / (safe_name(spec['title'], 'batch') + '.zip')
    saved = 0

    def publish(status='downloading', **extra):
        emit(status=status, items=items, **extra)

    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as zipper:
        for index, url in enumerate(urls):
            item = items[index]
            item['status'] = 'downloading'
            publish(progress=index / total * 94, speed=None, eta=None)
            workdir = directory / f'item-{index + 1:02d}'
            workdir.mkdir(exist_ok=True)

            def progress(fraction, speed, eta, index=index):
                done = min(fraction if fraction is not None else 0, 1)
                publish(progress=(index + done) / total * 94, speed=speed, eta=eta)

            def on_info(info, item=item):
                if not item['title'] and info.get('title'):
                    item['title'] = str(info['title'])[:160]

            try:
                fetch_best(url, workdir, mode, progress, on_info)
                # Move each finished item into the archive right away so disk use stays at ~1x.
                for file in produced_files(workdir):
                    zipper.write(file, f'{index + 1:02d} - {file.relative_to(workdir).as_posix()}')
                item['status'] = 'completed'
                item['title'] = item['title'] or url
                saved += 1
            except Exception as exc:
                message = str(exc)
                if 'unsupported url' in message.lower():
                    item['error'] = 'This site is not supported.'
                else:
                    item['error'] = friendly_error(message)
                item['status'] = 'failed'
            finally:
                shutil.rmtree(workdir, ignore_errors=True)
            publish(progress=(index + 1) / total * 94, speed=None, eta=None)
        if saved and saved < total:
            report = '\n'.join(f"{i['url']}\n    {i['error']}" for i in items if i['status'] == 'failed')
            zipper.writestr('failed-links.txt', report + '\n')
    if not saved:
        archive.unlink(missing_ok=True)
        emit(status='failed', items=items, error='None of the links could be downloaded. Check each link below.', speed=None, eta=None)
        sys.exit(1)
    emit(status='completed', items=items, progress=100, filename=archive.name, path=str(archive),
         size=archive.stat().st_size, speed=None, eta=None)


if __name__ == '__main__':
    try:
        request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        batch(request) if request['engine'] == 'batch' else download(request)
    except Exception as exc:
        emit(status='failed', error=friendly_error(str(exc)), speed=None, eta=None)
        sys.exit(1)
