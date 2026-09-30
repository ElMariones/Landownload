import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from .config import DATA, ROOT, WORKERS, RETENTION

ACTIVE = {'queued', 'downloading', 'processing'}


class JobManager:
    def __init__(self, data=DATA, workers=WORKERS):
        self.data = data
        self.data.mkdir(parents=True, exist_ok=True)
        self.db = self.data / 'history.sqlite3'
        self.lock = threading.RLock()
        self.processes = {}
        self.pool = ThreadPoolExecutor(max_workers=workers)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        for job in self.list():
            if job['status'] in ACTIVE:
                self.update(job['id'], status='failed', error='The server restarted. Inspect the link and try again.')
        self.cleanup()

    def connect(self):
        return sqlite3.connect(self.db, timeout=15)

    def list(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM jobs ORDER BY rowid DESC')]

    def get(self, job_id):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM jobs WHERE id = ?', (job_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def update(self, job_id, **changes):
        with self.lock:
            job = self.get(job_id)
            if not job or job['status'] == 'cancelled':
                return
            job.update(changes)
            with self.connect() as db:
                db.execute('UPDATE jobs SET payload = ? WHERE id = ?', (json.dumps(job), job_id))

    def create(self, media, option, owner=''):
        job = {'owner': owner, 'title': media['title'], 'platform': media['platform'], 'url': media['url'],
               'quality': option['label'], 'kind': option['kind'], 'ext': option['ext']}
        return self.enqueue(job, {'engine': media['engine'], 'url': media['url'], 'title': media['title'], 'option': option})

    def create_batch(self, urls, mode, owner=''):
        title = f'Batch of {len(urls)} links'
        job = {'owner': owner, 'title': title, 'platform': 'Batch', 'url': urls[0],
               'quality': 'Best audio · MP3' if mode == 'audio' else 'Best quality', 'kind': 'batch', 'ext': 'zip',
               'items': [{'url': url, 'status': 'queued', 'title': None, 'error': None} for url in urls]}
        return self.enqueue(job, {'engine': 'batch', 'urls': urls, 'mode': mode, 'title': title,
                                  'option': {'id': 'batch', 'ext': 'zip'}})

    def enqueue(self, fields, request):
        with self.lock:
            if sum(j['status'] in ACTIVE for j in self.list()) >= 12:
                raise ValueError('The queue is full. Wait for a download to finish.')
            job_id = uuid.uuid4().hex
            directory = self.data / job_id
            directory.mkdir()
            job = {'id': job_id, **fields, 'status': 'queued', 'progress': 0, 'speed': None, 'eta': None,
                   'created': time.time(), 'size': None, 'filename': None, 'error': None}
            with self.connect() as db:
                db.execute('INSERT INTO jobs VALUES (?, ?)', (job_id, json.dumps(job)))
            spec = directory / 'request.json'
            spec.write_text(json.dumps({'directory': str(directory), **request}), encoding='utf-8')
            self.pool.submit(self.run, job_id, spec)
            return job

    def run(self, job_id, spec):
        process = None
        try:
            with self.lock:
                if self.get(job_id)['status'] == 'cancelled':
                    return
                self.update(job_id, status='downloading')
                process = subprocess.Popen([sys.executable, '-m', 'backend.worker', str(spec)], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                         start_new_session=os.name != 'nt', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                self.processes[job_id] = process
            last_update = 0
            for line in process.stdout:
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict) or 'status' not in event:
                        continue
                    if time.time() - last_update > .4 or event['status'] in ('completed', 'failed', 'processing'):
                        self.update(job_id, **event)
                        last_update = time.time()
                except (ValueError, TypeError):
                    continue
            process.wait()
            current = self.get(job_id)
            if current and current['status'] in ACTIVE:
                self.update(job_id, status='failed', error='The download stopped before a file was produced. Try again.')
        except Exception:
            self.update(job_id, status='failed', error='Could not start the download process. Restart the server and try again.')
        finally:
            with self.lock:
                self.processes.pop(job_id, None)
            spec.unlink(missing_ok=True)

    def cancel(self, job_id):
        with self.lock:
            job = self.get(job_id)
            if not job:
                raise KeyError(job_id)
            if job['status'] not in ACTIVE:
                return
            self.update(job_id, status='cancelled', speed=None, eta=None)
            process = self.processes.get(job_id)
            if process and process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    os.killpg(process.pid, signal.SIGTERM)

    def remove(self, job_id):
        with self.lock:
            job = self.get(job_id)
            if not job:
                raise KeyError(job_id)
            if job['status'] in ACTIVE or job_id in self.processes:
                raise ValueError('Cancel this download and wait for it to stop before removing it.')
            # UUIDs come from the DB; resolve before any recursive deletion.
            directory = (self.data / job_id).resolve()
            if directory.parent != self.data.resolve():
                raise ValueError('Invalid download directory.')
            if directory.exists():
                shutil.rmtree(directory)
            with self.connect() as db:
                db.execute('DELETE FROM jobs WHERE id = ?', (job_id,))

    def cleanup(self):
        for job in self.list():
            if job['status'] not in ACTIVE and job['created'] < time.time() - RETENTION:
                try:
                    self.remove(job['id'])
                except (ValueError, OSError):
                    pass

    def close(self):
        for job in self.list():
            if job['status'] in ACTIVE:
                self.cancel(job['id'])
        self.pool.shutdown(wait=True, cancel_futures=True)


def public_job(job):
    return {k: v for k, v in job.items() if k not in ('path', 'owner')}
