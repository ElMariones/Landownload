"""X / Twitter with a fallback for posts X hides from logged-out clients.

yt-dlp's own extractor runs first. When it fails (hidden posts come back as a
"tombstone", photo-only posts have no video), the public FxTwitter API is
used instead; it still returns every rendition and original-size photos.
"""
import re
from urllib.parse import parse_qs

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.extractor.twitter import TwitterIE
from yt_dlp.utils import ExtractorError, float_or_none, int_or_none, traverse_obj, url_or_none


class XIE(InfoExtractor):
    IE_NAME = 'X'
    _VALID_URL = TwitterIE._VALID_URL
    _TESTS = [{
        'url': 'https://x.com/historyinmemes/status/1790637656616943991',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        tweet_id, index = self._match_valid_url(url).group('id', 'index')
        try:
            return self._downloader.get_info_extractor(TwitterIE.ie_key()).extract(url)
        except ExtractorError as native_error:
            native = native_error

        data = self._download_json(f'https://api.fxtwitter.com/status/{tweet_id}', tweet_id,
                                   'Retrying through FxTwitter', fatal=False, expected_status=404)
        tweet = traverse_obj(data, ('tweet', {dict})) or {}
        media = traverse_obj(tweet, ('media', 'all', lambda _, v: v.get('type') in ('video', 'gif', 'photo')))
        if not media:
            raise native

        author = traverse_obj(tweet, ('author', 'name')) or traverse_obj(tweet, ('author', 'screen_name')) or 'X'
        text = re.sub(r'\s+', ' ', tweet.get('text') or '').strip()
        common = {
            'title': f'{author} - {text[:80]}' if text else f'{author} - {tweet_id}',
            'description': tweet.get('text'),
            'uploader': author,
            'uploader_id': traverse_obj(tweet, ('author', 'screen_name')),
            'timestamp': int_or_none(tweet.get('created_timestamp')),
            'like_count': int_or_none(tweet.get('likes')),
            'repost_count': int_or_none(tweet.get('retweets')),
            'webpage_url': f'https://x.com/i/status/{tweet_id}',
        }
        entries = [{**common, **self._entry(item, tweet_id)} for item in media]
        if index:
            position = int(index) - 1
            if not 0 <= position < len(entries):
                raise ExtractorError(f'This post has no media #{index}.', expected=True)
            entries = [entries[position]]
        if len(entries) == 1:
            return {**entries[0], 'id': tweet_id}
        return self.playlist_result(entries, tweet_id, common['title'], multi_video=True, **{
            k: common[k] for k in ('uploader', 'timestamp')})

    def _entry(self, item, tweet_id):
        media_id = str(item.get('id') or tweet_id)
        if item['type'] == 'photo':
            # Photos are ".../ID.jpg?name=x" or, for cards, ".../ID?format=jpg&name=x".
            base, _, query = item['url'].partition('?')
            fmt = parse_qs(query).get('format', [None])[0]
            ext = (fmt or base.rsplit('/', 1)[-1].rpartition('.')[2]).lower()
            ext = ext if ext in ('jpg', 'jpeg', 'png', 'webp', 'gif') else 'jpg'
            size_url = f'{base}?format={fmt}&name=' if fmt else f'{base}?name='
            return {
                'id': media_id,
                'thumbnail': size_url + 'small',
                'formats': [{
                    'url': size_url + 'orig',
                    'format_id': 'orig',
                    'ext': ext,
                    'width': int_or_none(item.get('width')),
                    'height': int_or_none(item.get('height')),
                    # Codecs stay unknown: yt-dlp treats vcodec=acodec='none' as a storyboard and never picks it.
                }],
            }

        formats = []
        for variant in traverse_obj(item, ('variants', lambda _, v: url_or_none(v['url']))) or []:
            if 'mpegurl' in str(variant.get('content_type')).lower() or '.m3u8' in variant['url']:
                formats.extend(self._extract_m3u8_formats(variant['url'], media_id, 'mp4', m3u8_id='hls', fatal=False))
                continue
            size = re.search(r'/(\d+)x(\d+)/', variant['url'])
            bitrate = int_or_none(variant.get('bitrate'), scale=1000)
            formats.append({
                'url': variant['url'],
                'format_id': f'http-{bitrate}' if bitrate else 'http',
                'ext': 'mp4',
                'tbr': bitrate,
                'width': int(size.group(1)) if size else None,
                'height': int(size.group(2)) if size else None,
                'vcodec': 'avc1' if item['type'] == 'video' else None,
                'acodec': 'none' if item['type'] == 'gif' else 'mp4a',
            })
        if not formats and url_or_none(item.get('url')):
            formats.append({'url': item['url'], 'format_id': 'http', 'ext': 'mp4',
                            'width': int_or_none(item.get('width')), 'height': int_or_none(item.get('height'))})
        return {
            'id': media_id,
            'thumbnail': url_or_none(item.get('thumbnail_url')),
            'duration': float_or_none(item.get('duration')),
            'formats': formats,
        }
