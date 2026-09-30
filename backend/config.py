import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DATA = Path(os.getenv('LANDOWNLOAD_DATA', str(ROOT / 'data'))).resolve()
HOST = os.getenv('LANDOWNLOAD_HOST', '127.0.0.1')
PORT = int(os.getenv('LANDOWNLOAD_PORT', '8000'))
TOKEN = os.getenv('LANDOWNLOAD_TOKEN', '')
COOKIES = os.getenv('LANDOWNLOAD_COOKIES', '')
FFMPEG = os.getenv('LANDOWNLOAD_FFMPEG', '')
WORKERS = max(1, min(4, int(os.getenv('LANDOWNLOAD_WORKERS', '2'))))
RETENTION = max(1, int(os.getenv('LANDOWNLOAD_RETENTION_HOURS', '48'))) * 3600
# Websites allowed to call the API from another origin, e.g. the GitHub Pages copy of the UI.
ORIGINS = [o.strip().rstrip('/') for o in os.getenv('LANDOWNLOAD_ORIGINS', '').split(',') if o.strip()]


def ffmpeg_available():
    return bool(shutil.which('ffmpeg', path=FFMPEG or None))


def cookie_args():
    return ['--cookies', COOKIES] if COOKIES else []


def yt_args():
    args = ['--ignore-config', '--no-playlist', '--no-warnings', '--no-colors',
            '--socket-timeout', '20', '--retries', '2', '--extractor-retries', '2',
            '--js-runtimes', 'node', *cookie_args()]
    if FFMPEG:
        args += ['--ffmpeg-location', FFMPEG]
    return args
