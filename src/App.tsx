import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, type Health, type Job, type Media, type Site } from './api';
import { looksLikeMany } from './lib/links';
import { HOSTED, loadConnection, saveConnection, SERVER_URL } from './lib/server';
import { Masthead } from './components/Masthead';
import { SingleLink } from './components/SingleLink';
import { BatchComposer } from './components/BatchComposer';
import { Preview, PreviewPlaceholder } from './components/Preview';
import { Tray } from './components/Tray';
import { SiteIndex } from './components/SiteIndex';
import { Unlock } from './components/Unlock';
import { ServerOff } from './components/ServerOff';

type Mode = 'single' | 'batch';
const ACTIVE = new Set(['queued', 'downloading', 'processing']);

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  const [sites, setSites] = useState<Site[]>([]);
  const [mode, setMode] = useState<Mode>('single');
  const [url, setUrl] = useState('');
  const [batchText, setBatchText] = useState('');
  const [media, setMedia] = useState<Media | null>(null);
  const [inspecting, setInspecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [needsServer, setNeedsServer] = useState(() => HOSTED && !loadConnection().url);
  const [pending, setPending] = useState<string | null>(null);
  // Only files requested from this tab are saved automatically when they finish.
  const ownJobs = useRef(new Set<string>());
  const saved = useRef(new Set<string>());
  const inspectRun = useRef(0);

  const loadHealth = useCallback(async () => {
    if (HOSTED && !loadConnection().url) {
      setNeedsServer(true);
      return;
    }
    try {
      const next = await api.health();
      setHealth(next);
      setOffline(false);
      setNeedsServer(false);
      if (!next.auth_required) setSites(await api.sites());
    } catch (err) {
      setOffline(true);
      // A typed-in address that never answered is probably wrong; a built-in one is just switched off.
      if (HOSTED && !SERVER_URL && !(err instanceof ApiError && err.status === 0)) setNeedsServer(true);
    }
  }, []);

  // While the server is off, keep checking so the page comes back by itself.
  useEffect(() => {
    if (!offline) return;
    const timer = window.setInterval(loadHealth, 8000);
    return () => window.clearInterval(timer);
  }, [offline, loadHealth]);

  useEffect(() => {
    loadHealth();
  }, [loadHealth]);

  const refreshJobs = useCallback(async () => {
    try {
      const next = await api.jobs();
      setJobs(next);
      for (const job of next) {
        if (job.status === 'completed' && ownJobs.current.has(job.id) && !saved.current.has(job.id)) {
          saved.current.add(job.id);
          const link = document.createElement('a');
          link.href = api.fileUrl(job.id);
          link.download = job.filename ?? '';
          document.body.appendChild(link);
          link.click();
          link.remove();
        }
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setHealth((h) => (h ? { ...h, auth_required: true } : h));
      if (err instanceof ApiError && [0, 502, 503, 504].includes(err.status)) setOffline(true);
    }
  }, []);

  const busy = jobs.some((j) => ACTIVE.has(j.status));
  useEffect(() => {
    if (!health || health.auth_required) return;
    refreshJobs();
    const timer = window.setInterval(refreshJobs, busy ? 900 : 5000);
    return () => window.clearInterval(timer);
  }, [health, busy, refreshJobs]);

  const inspect = useCallback(async (target: string) => {
    const link = target.trim();
    if (!link) return;
    const run = ++inspectRun.current;
    setInspecting(true);
    setError(null);
    setMedia(null);
    try {
      const result = await api.inspect(link);
      if (run === inspectRun.current) setMedia(result);
    } catch (err) {
      if (run === inspectRun.current) setError(err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      if (run === inspectRun.current) setInspecting(false);
    }
  }, []);

  const handlePasteMany = useCallback((text: string) => {
    setMode('batch');
    setBatchText((current) => (current.trim() ? `${current.trim()}\n` : '') + text.replace(/\s+(?=https?:\/\/)/gi, '\n').trim());
  }, []);

  // Ctrl+V anywhere on the page (outside inputs) drops the link straight in.
  useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && (target.closest('input, textarea') || target.isContentEditable)) return;
      const text = event.clipboardData?.getData('text')?.trim();
      if (!text || !/https?:\/\//i.test(text)) return;
      event.preventDefault();
      if (looksLikeMany(text)) {
        handlePasteMany(text);
      } else {
        setMode('single');
        setUrl(text);
        inspect(text);
      }
    }
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [inspect, handlePasteMany]);

  async function startDownload(optionId: string) {
    if (!media) return;
    setPending(optionId);
    setError(null);
    try {
      const job = await api.download(media.id, optionId);
      ownJobs.current.add(job.id);
      await refreshJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the download.');
    } finally {
      setPending(null);
    }
  }

  async function startBatch(urls: string[], batchMode: 'video' | 'audio') {
    const job = await api.batch(urls, batchMode);
    ownJobs.current.add(job.id);
    await refreshJobs();
  }

  async function cancel(id: string) {
    await api.cancel(id).catch(() => undefined);
    refreshJobs();
  }

  async function remove(id: string) {
    await api.remove(id).catch(() => undefined);
    refreshJobs();
  }

  async function clearFinished() {
    await Promise.all(jobs.filter((j) => !ACTIVE.has(j.status)).map((j) => api.remove(j.id).catch(() => undefined)));
    refreshJobs();
  }

  function changeServer() {
    saveConnection({ ...loadConnection(), session: '' });
    setJobs([]);
    setMedia(null);
    setNeedsServer(true);
  }

  if (needsServer || health?.auth_required) {
    return <Unlock onUnlocked={loadHealth} />;
  }
  if (offline) {
    return <ServerOff onRetry={loadHealth} />;
  }

  return (
    <div className="shell">
      <div className="grain" aria-hidden />
      <Masthead health={health} offline={offline} onChangeServer={HOSTED && !SERVER_URL ? changeServer : undefined} />

      <main className="workbench">
        <section className="intake" aria-label="Add media">
          <div className="modes" role="tablist" aria-label="Download mode">
            <button role="tab" aria-selected={mode === 'single'} className={mode === 'single' ? 'on' : ''} onClick={() => setMode('single')}>
              One link
            </button>
            <button role="tab" aria-selected={mode === 'batch'} className={mode === 'batch' ? 'on' : ''} onClick={() => setMode('batch')}>
              Batch → ZIP
            </button>
            <span className="modes-hint">
              or press <kbd>Ctrl</kbd> <kbd>V</kbd> anywhere
            </span>
          </div>

          {mode === 'single' ? (
            <>
              <SingleLink value={url} onChange={setUrl} onSubmit={() => inspect(url)} busy={inspecting} onPasteMany={handlePasteMany} />
              {error && (
                <p className="alert" role="alert">
                  {error}
                </p>
              )}
              {media ? (
                <Preview media={media} pending={pending} onDownload={startDownload} ffmpeg={health?.ffmpeg ?? true} />
              ) : (
                <PreviewPlaceholder loading={inspecting} />
              )}
            </>
          ) : (
            <BatchComposer value={batchText} onChange={setBatchText} onSubmit={startBatch} ffmpeg={health?.ffmpeg ?? true} />
          )}
        </section>

        <Tray jobs={jobs} onCancel={cancel} onRemove={remove} onClear={clearFinished} retentionHours={health?.retention_hours} />
      </main>

      <SiteIndex sites={sites} />
    </div>
  );
}
