import asyncio
import hashlib
import hmac
import importlib.metadata
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from typing import Literal

from pydantic import BaseModel, Field

from . import config
from .jobs import JobManager, public_job
from .media import inspect_media, get_media, MediaError
from .network import public_stream
from .security import UnsafeURL, validate_url
from .sites import catalogue

jobs = None
# Derived from the access key so remote sessions survive restarts; random when running local-only.
SESSION_KEY = hashlib.sha256(b'landownload-session:' + config.TOKEN.encode()).digest() if config.TOKEN else secrets.token_bytes(32)
SESSION_SECONDS = 30 * 86400
INSPECT_SLOTS = asyncio.Semaphore(2)
LOOPBACK = {'localhost', '127.0.0.1', '::1'}
ALLOWED_ORIGINS = {f'http://{host}:{port}' for host in ('localhost', '127.0.0.1', '[::1]') for port in (8000, 5173, 4173, config.PORT)}
ALLOWED_ORIGINS.update(config.ORIGINS)


@asynccontextmanager
async def lifespan(app):
    global jobs
    if config.HOST not in ('localhost', '127.0.0.1', '::1') and len(config.TOKEN) < 24:
        raise RuntimeError('Set LANDOWNLOAD_TOKEN to at least 24 characters before exposing the server to a network.')
    jobs = JobManager()
    async def cleanup_loop():
        while True:
            await asyncio.sleep(600)
            await asyncio.to_thread(jobs.cleanup)
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    await asyncio.to_thread(jobs.close)


app = FastAPI(title='Landownload', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def new_session():
    expiry = str(int(time.time()) + SESSION_SECONDS)
    return expiry + '.' + hmac.new(SESSION_KEY, expiry.encode(), hashlib.sha256).hexdigest()


def valid_session(cookie):
    try:
        expiry, signature = cookie.split('.')
        expected = hmac.new(SESSION_KEY, expiry.encode(), hashlib.sha256).hexdigest()
        return int(expiry) > time.time() and hmac.compare_digest(signature, expected)
    except (ValueError, AttributeError):
        return False


@app.middleware('http')
async def private_access(request: Request, call_next):
    origin = request.headers.get('origin')
    # Without an access key the server only answers on loopback, which also blocks DNS rebinding
    # and a tunnel accidentally exposing an unprotected instance.
    if request.url.hostname not in LOOPBACK and not config.TOKEN:
        return JSONResponse({'detail': 'Set LANDOWNLOAD_TOKEN to use Landownload from another device.'}, status_code=403)
    if request.url.path.startswith('/api/'):
        same_origin = origin and urlsplit(origin).netloc == request.headers.get('host')
        if origin and origin not in ALLOWED_ORIGINS and not same_origin:
            return JSONResponse({'detail': 'This website is not allowed to use this server. Add it to LANDOWNLOAD_ORIGINS.'}, status_code=403)
        if request.method not in ('GET', 'HEAD') and request.headers.get('content-type', '').split(';')[0] != 'application/json':
            return JSONResponse({'detail': 'Use application/json.'}, status_code=415)
        if config.TOKEN and request.url.path not in ('/api/health', '/api/auth') and not authorized(request):
            return JSONResponse({'detail': 'Unlock your private workspace first.'}, status_code=401)
    response = await call_next(request)
    response.headers.update({'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
                             'X-Frame-Options': 'DENY', 'Cache-Control': 'no-store'})
    if not request.url.path.startswith('/api/'):
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' ws://127.0.0.1:* ws://localhost:*; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
    return response


def authorized(request: Request):
    # Cookie for the bundled UI, bearer header for the hosted UI, query param for <img>/<a> GETs.
    bearer = request.headers.get('authorization', '').removeprefix('Bearer ').strip()
    query = request.query_params.get('s') if request.method in ('GET', 'HEAD') else None
    return any(valid_session(value) for value in (request.cookies.get('landownload_session'), bearer, query) if value)


app.add_middleware(CORSMiddleware, allow_origins=sorted(ALLOWED_ORIGINS), allow_methods=['GET', 'POST', 'DELETE'],
                   allow_headers=['Authorization', 'Content-Type'], expose_headers=['Content-Disposition'],
                   allow_private_network=True, max_age=600)


class LinkRequest(BaseModel):
    url: str = Field(min_length=8, max_length=4096)


class DownloadRequest(BaseModel):
    media_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    option_id: str = Field(max_length=100)


class BatchRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=50)
    mode: Literal['video', 'audio'] = 'video'


class AuthRequest(BaseModel):
    token: str = Field(max_length=1024)


@app.get('/api/health')
def health(request: Request):
    return {'status': 'ok', 'ffmpeg': config.ffmpeg_available(), 'cookies': bool(config.COOKIES),
            'auth_required': bool(config.TOKEN) and not authorized(request),
            'engines': {name: importlib.metadata.version(name) for name in ('yt-dlp', 'gallery-dl')},
            'retention_hours': config.RETENTION // 3600, 'workers': config.WORKERS}


@app.post('/api/auth')
def authenticate(body: AuthRequest, response: Response, request: Request):
    if not config.TOKEN or not secrets.compare_digest(body.token, config.TOKEN):
        raise HTTPException(401, 'That access key is incorrect.')
    session = new_session()
    response.set_cookie('landownload_session', session, httponly=True, samesite='strict',
                        secure=request.url.scheme == 'https', max_age=SESSION_SECONDS)
    return {'ok': True, 'session': session}


@app.post('/api/inspect')
async def inspect(body: LinkRequest):
    if INSPECT_SLOTS.locked():
        raise HTTPException(429, 'Two previews are already loading. Try again shortly.')
    async with INSPECT_SLOTS:
        try:
            return await asyncio.to_thread(inspect_media, body.url)
        except (MediaError, UnsafeURL) as exc:
            raise HTTPException(422, str(exc)) from exc


@app.get('/api/media/{media_id}/thumbnail')
def thumbnail(media_id: str):
    try:
        media = get_media(media_id)
        if not media.get('thumbnail'):
            raise ValueError('No preview available.')
        with public_stream(media['thumbnail']) as remote:
            content_type = remote.headers.get('content-type', '').split(';')[0]
            if content_type not in ('image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/avif'):
                raise ValueError('Unsupported preview type.')
            content = bytearray()
            for chunk in remote.iter_bytes(64 * 1024):
                content.extend(chunk)
                if len(content) > 8 * 1024 * 1024:
                    raise ValueError('Preview too large.')
            return Response(bytes(content), media_type=content_type)
    except Exception as exc:
        raise HTTPException(404, 'Preview unavailable.') from exc


@app.post('/api/downloads', status_code=201)
def create_download(body: DownloadRequest):
    try:
        media = get_media(body.media_id)
        option = next((o for o in media['options'] if o['id'] == body.option_id), None)
        if not option:
            raise ValueError('Choose a format from this preview.')
        return public_job(jobs.create(media, option))
    except (ValueError, MediaError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/api/sites')
def sites():
    return catalogue()


@app.post('/api/batches', status_code=201)
async def create_batch(body: BatchRequest):
    urls = list(dict.fromkeys(u.strip() for u in body.urls if u.strip()))
    if not urls:
        raise HTTPException(422, 'Add at least one link, one per line.')

    def check(url):
        try:
            validate_url(url)
            return None
        except UnsafeURL as exc:
            return f'{url[:80]} — {exc}'
    problems = [p for p in await asyncio.gather(*(asyncio.to_thread(check, u) for u in urls)) if p]
    if problems:
        raise HTTPException(422, 'Fix these links first: ' + ' · '.join(problems[:5]))
    try:
        return public_job(jobs.create_batch(urls, body.mode))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/api/downloads')
def list_downloads():
    return [public_job(j) for j in jobs.list()]


@app.post('/api/downloads/{job_id}/cancel')
def cancel_download(job_id: str):
    try:
        jobs.cancel(job_id)
        return {'ok': True}
    except KeyError as exc:
        raise HTTPException(404, 'Download not found.') from exc


@app.delete('/api/downloads/{job_id}')
def remove_download(job_id: str):
    try:
        jobs.remove(job_id)
        return {'ok': True}
    except KeyError as exc:
        raise HTTPException(404, 'Download not found.') from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get('/api/downloads/{job_id}/file')
def download_file(job_id: str):
    job = jobs.get(job_id)
    if not job or job['status'] != 'completed' or not job.get('path'):
        raise HTTPException(404, 'This file is not ready.')
    file = Path(job['path']).resolve()
    if not file.is_relative_to(jobs.data.resolve() / job_id) or not file.is_file():
        raise HTTPException(410, 'This file has expired or been removed.')
    return FileResponse(file, filename=job['filename'], media_type='application/octet-stream')


if (config.ROOT / 'dist').exists():
    app.mount('/', StaticFiles(directory=config.ROOT / 'dist', html=True), name='frontend')
