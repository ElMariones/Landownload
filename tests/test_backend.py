import os
import tempfile

os.environ['LANDOWNLOAD_DATA'] = tempfile.mkdtemp(prefix='landownload-test-')
os.environ['LANDOWNLOAD_TOKEN'] = 'test-access-key-with-enough-length'
os.environ['LANDOWNLOAD_ORIGINS'] = 'https://someone.github.io'

import pytest
from fastapi.testclient import TestClient

from backend import media
from backend.app import app
from yt_dlp_plugins.extractor.landownload_hosts import NuxtVideoIE


@pytest.fixture(autouse=True)
def ffmpeg(monkeypatch):
    monkeypatch.setattr(media, 'ffmpeg_available', lambda: True)


def test_unknown_codecs_still_produce_options():
    # HLS renditions with no codec metadata at all, as many hosts publish them.
    info = {'formats': [
        {'format_id': 'hls-360p', 'height': 360, 'ext': 'mp4', 'protocol': 'm3u8_native'},
        {'format_id': 'hls-1080p', 'height': 1080, 'ext': 'mp4', 'protocol': 'm3u8_native'},
        {'format_id': 'high', 'ext': 'mp4', 'protocol': 'https'},
    ]}
    options = media.video_options(info)
    labels = [o['label'] for o in options if o['kind'] == 'video']
    assert labels == ['1080p', '360p', 'High quality']
    assert all(o['audio'] for o in options if o['kind'] == 'video')


def test_direct_file_beats_duplicate_hls_rendition():
    info = {'formats': [
        {'format_id': 'hls-9156', 'height': 1080, 'fps': 30, 'ext': 'mp4', 'protocol': 'm3u8_native', 'vcodec': 'avc1', 'acodec': 'mp4a'},
        {'format_id': '1080p', 'height': 1080, 'ext': 'mp4', 'protocol': 'https'},
        {'format_id': 'original', 'height': 2160, 'ext': 'mp4', 'protocol': 'https', 'quality': 10},
        {'format_id': 'hls-25192', 'height': 2160, 'ext': 'mp4', 'protocol': 'm3u8_native'},
    ]}
    video = [o['id'] for o in media.video_options(info) if o['kind'] == 'video']
    assert video == ['v-original', 'v-1080p']


def test_silent_video_is_merged_with_matching_audio():
    info = {'formats': [
        {'format_id': '137', 'height': 1080, 'ext': 'mp4', 'vcodec': 'avc1.640028', 'acodec': 'none'},
        {'format_id': '140', 'ext': 'm4a', 'vcodec': 'none', 'acodec': 'mp4a.40.2', 'abr': 129},
        {'format_id': '140-drc', 'ext': 'm4a', 'vcodec': 'none', 'acodec': 'mp4a.40.2', 'abr': 129},
    ]}
    options = media.video_options(info)
    assert options[0]['selector'] == '137+140' and options[0]['ext'] == 'mp4'
    assert [o['id'] for o in options if o['kind'] == 'audio'] == ['a-140', 'mp3']


def test_nuxt_payload_lookup_finds_the_requested_video():
    payload = {'data': {'page': {'related': [{'_id': 'other', 'videoUrl': 'x'}],
                                 'video': {'_id': '6abd0fc31a032641760d21c2', 'videoUrl': 'https://cdn/v.mp4'}}}}
    assert NuxtVideoIE._find_video(payload, '6abd0fc31a032641760d21c2')['videoUrl'] == 'https://cdn/v.mp4'
    assert NuxtVideoIE._find_video(payload, 'missing') is None


@pytest.fixture
def client():
    with TestClient(app, base_url='http://127.0.0.1:8000') as c:
        yield c


def unlock(client):
    session = client.post('/api/auth', json={'token': 'test-access-key-with-enough-length'}).json()['session']
    return {'Authorization': f'Bearer {session}'}


def test_remote_access_needs_a_session(client):
    assert client.get('/api/downloads').status_code == 401
    assert client.post('/api/auth', json={'token': 'wrong'}).status_code == 401
    assert client.get('/api/downloads', headers=unlock(client)).status_code == 200


def test_hosted_ui_origin_is_allowed_and_others_are_not(client):
    headers = unlock(client)
    allowed = client.get('/api/downloads', headers={**headers, 'Origin': 'https://someone.github.io'})
    assert allowed.status_code == 200
    assert allowed.headers['access-control-allow-origin'] == 'https://someone.github.io'
    assert client.get('/api/downloads', headers={**headers, 'Origin': 'https://evil.example'}).status_code == 403


def test_batch_rejects_private_and_malformed_links(client):
    client.headers.update(unlock(client))
    response = client.post('/api/batches', json={'urls': ['http://127.0.0.1/admin', 'ftp://example.com/x']})
    assert response.status_code == 422
    assert 'Local and private' in response.json()['detail']


def test_batch_size_is_capped(client):
    client.headers.update(unlock(client))
    response = client.post('/api/batches', json={'urls': [f'https://example.com/{i}' for i in range(51)]})
    assert response.status_code == 422


def test_sites_catalogue(client):
    sites = client.get('/api/sites', headers=unlock(client)).json()
    assert {'YouTube', 'X / Twitter', 'Instagram'} <= {s['name'] for s in sites}


def test_x_photo_urls_keep_card_format_and_request_original():
    import yt_dlp
    from yt_dlp_plugins.extractor.landownload_x import XIE
    ie = XIE(yt_dlp.YoutubeDL({'quiet': True}))
    card = ie._entry({'type': 'photo', 'id': '1', 'url': 'https://pbs.twimg.com/card_img/1/abc?format=jpg&name=small'}, '9')
    photo = ie._entry({'type': 'photo', 'id': '2', 'url': 'https://pbs.twimg.com/media/XYZ.png?name=small'}, '9')
    assert card['formats'][0]['url'] == 'https://pbs.twimg.com/card_img/1/abc?format=jpg&name=orig'
    assert photo['formats'][0]['url'] == 'https://pbs.twimg.com/media/XYZ.png?name=orig'
    assert photo['formats'][0]['ext'] == 'png'
    assert XIE.suitable('https://x.com/someone/status/1790637656616943991?s=20')


def test_multi_media_post_offers_each_item_and_a_zip():
    entries = [
        {'formats': [{'format_id': 'http-2176', 'height': 720, 'ext': 'mp4', 'vcodec': 'avc1', 'acodec': 'mp4a', 'filesize': 10}]},
        {'formats': [{'format_id': 'orig', 'ext': 'jpg', 'width': 1200, 'height': 800, 'filesize': 5}]},
    ]
    options = media.post_options(entries)
    assert [o['id'] for o in options] == ['post-all', 'item1-v-http-2176', 'item2-i-orig']
    assert options[0]['size'] == 15 and options[0]['kind'] == 'video'
    assert [o['playlist_items'] for o in options] == ['1:50', '1', '2']
    assert options[2]['label'] == 'Image 2 · 1200×800'


def test_each_browser_only_sees_its_own_downloads(client):
    from backend import app as app_module
    job = app_module.jobs.enqueue({'owner': 'browser-aaaa', 'title': 't', 'platform': 'p', 'url': 'u',
                                   'quality': 'q', 'kind': 'video', 'ext': 'mp4'},
                                  {'engine': 'none', 'url': 'u', 'title': 't', 'option': {}})
    auth = unlock(client)
    mine = client.get('/api/downloads', headers={**auth, 'X-Client-Id': 'browser-aaaa'}).json()
    theirs = client.get('/api/downloads', headers={**auth, 'X-Client-Id': 'browser-bbbb'}).json()
    assert [j['id'] for j in mine] == [job['id']] and 'owner' not in mine[0]
    assert theirs == []
    stranger = client.post(f"/api/downloads/{job['id']}/cancel", json={}, headers={**auth, 'X-Client-Id': 'browser-bbbb'})
    assert stranger.status_code == 404


def test_single_file_pages_without_a_formats_list_still_work():
    # The generic extractor returns one file as the result itself: url/ext, no "formats" list.
    info = {'url': 'https://cdn.example/v/123.mp4', 'ext': 'mp4', 'format_id': '0', 'title': 't'}
    options = media.video_options(info)
    assert [(o['id'], o['label'], o['selector']) for o in options if o['kind'] == 'video'] == [('v-0', 'Original', '0')]
    assert media.entry_options({'title': 'nothing here'}) == []
