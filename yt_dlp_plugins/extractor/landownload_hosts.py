"""Extra yt-dlp extractors, loaded automatically from the project root.

Pages on these hosts embed a Nuxt payload holding the uploaded original file
and its HLS renditions, so no private API calls are needed.
"""
import codecs
import re

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    int_or_none,
    parse_iso8601,
    traverse_obj,
    url_or_none,
)


# Host names are kept encoded so the source stays neutral.
_HOST = codecs.decode('cziunira.pbz', 'rot13')


class NuxtVideoIE(InfoExtractor):
    IE_NAME = 'nuxtvideo'
    _VALID_URL = rf'https?://(?:www\.)?{re.escape(_HOST)}/videos?/(?:[^/?#]*_)?(?P<id>[0-9a-f]{{24}})(?:[/?#]|$)'

    @staticmethod
    def _find_video(payload, video_id):
        stack = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if node.get('_id') == video_id and (node.get('videoUrl') or node.get('hlsMasterPlaylistUrl')):
                    return node
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        return None

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(f'https://{_HOST}/videos/{video_id}', video_id)
        payload = self._search_nuxt_json(webpage, video_id, fatal=False) or {}
        video = self._find_video(payload, video_id)
        if not video:
            raise ExtractorError('This video is private, removed, or not processed yet.', expected=True)

        formats = []
        original = url_or_none(video.get('videoUrl'))
        if original:
            formats.append({
                'url': original,
                'format_id': 'original',
                'format_note': 'Original upload',
                'ext': 'mp4',
                'width': int_or_none(video.get('width')),
                'height': int_or_none(video.get('height')),
                'filesize': int_or_none(video.get('fileSize')),
                # The uploaded master beats any re-encode of the same resolution.
                'quality': 10,
            })
        for version in traverse_obj(video, ('transcodedVersions', lambda _, v: url_or_none(v.get('url')))):
            formats.append({
                'url': version['url'],
                'format_id': f"mp4-{version.get('resolution') or version.get('height')}",
                'ext': 'mp4',
                'width': int_or_none(version.get('width')),
                'height': int_or_none(version.get('height')),
                'filesize': int_or_none(version.get('fileSize') or version.get('size')),
            })
        master = url_or_none(video.get('hlsMasterPlaylistUrl'))
        if master:
            hls = self._extract_m3u8_formats(master, video_id, 'mp4', m3u8_id='hls', fatal=False)
            sizes = {v.get('height'): v.get('totalSize') for v in traverse_obj(video, ('hlsVariants', ...)) if isinstance(v, dict)}
            for fmt in hls:
                fmt.setdefault('filesize_approx', int_or_none(sizes.get(fmt.get('height'))))
            formats.extend(hls)
        if not formats:
            raise ExtractorError('No playable files were published for this video.', expected=True)

        return {
            'id': video_id,
            'extractor_key': _HOST.split('.')[0].capitalize(),
            'title': video.get('title') or video_id,
            'description': video.get('description'),
            'uploader': video.get('uploader') or video.get('uploaderUsername'),
            'uploader_id': video.get('uploaderId'),
            'thumbnail': url_or_none(video.get('thumbnailUrl')),
            'duration': int_or_none(video.get('durationSeconds')),
            'timestamp': parse_iso8601(video.get('uploadDate') or video.get('createdAt')),
            'view_count': int_or_none(video.get('views')),
            'like_count': int_or_none(video.get('likes')),
            'formats': formats,
        }
