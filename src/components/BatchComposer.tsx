import { useMemo, useRef, useState } from 'react';
import { FileArchive, LoaderCircle, Music, Film } from 'lucide-react';
import { hostOf, MAX_BATCH, parseLines, uniqueUrls } from '../lib/links';

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (urls: string[], mode: 'video' | 'audio') => Promise<void>;
  ffmpeg: boolean;
}

export function BatchComposer({ value, onChange, onSubmit, ffmpeg }: Props) {
  const [mode, setMode] = useState<'video' | 'audio'>('video');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<number | null>(null);
  const gutter = useRef<HTMLDivElement>(null);

  const lines = useMemo(() => parseLines(value), [value]);
  const urls = useMemo(() => uniqueUrls(lines), [lines]);
  const invalid = lines.filter((l) => !l.url).length;
  const dupes = lines.filter((l) => l.duplicate).length;
  const over = urls.length > MAX_BATCH;
  const rowCount = Math.max(8, value.split('\n').length);
  const byLine = new Map(lines.map((l) => [l.line, l]));

  async function submit() {
    setSending(true);
    setError(null);
    try {
      await onSubmit(urls, mode);
      setSent(urls.length);
      onChange('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the batch.');
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="batch">
      <div className="batch-editor">
        <div className="gutter" ref={gutter} aria-hidden>
          {Array.from({ length: rowCount }, (_, i) => {
            const line = byLine.get(i + 1);
            const state = !line ? '' : !line.url ? 'bad' : line.duplicate ? 'dup' : 'good';
            return (
              <span key={i} className={state} title={line ? (line.url ? hostOf(line.url) : 'Not a link') : undefined}>
                {i + 1}
              </span>
            );
          })}
        </div>
        <textarea
          aria-label="Links, one per line"
          spellCheck={false}
          rows={8}
          placeholder={'One link per line…\nhttps://www.youtube.com/watch?v=…\nhttps://x.com/…/status/…\nhttps://www.instagram.com/p/…\nhttps://www.tiktok.com/@…/video/…'}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setSent(null);
          }}
          onScroll={(e) => {
            if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop;
          }}
        />
      </div>

      <div className="batch-bar">
        <div className="tally">
          <strong>{urls.length}</strong> link{urls.length === 1 ? '' : 's'} ready
          {invalid > 0 && <span className="bad">{invalid} not a link</span>}
          {dupes > 0 && <span className="dup">{dupes} duplicate{dupes > 1 ? 's' : ''} skipped</span>}
          {over && <span className="bad">max {MAX_BATCH} per batch</span>}
        </div>
        <div className="switch" role="radiogroup" aria-label="Batch format">
          <button role="radio" aria-checked={mode === 'video'} className={mode === 'video' ? 'on' : ''} onClick={() => setMode('video')}>
            <Film size={14} /> Best video
          </button>
          <button role="radio" aria-checked={mode === 'audio'} className={mode === 'audio' ? 'on' : ''} onClick={() => setMode('audio')}>
            <Music size={14} /> {ffmpeg ? 'MP3 audio' : 'Best audio'}
          </button>
        </div>
        <button className="go wide" disabled={!urls.length || over || sending} onClick={submit}>
          {sending ? <LoaderCircle className="spin" size={18} /> : <FileArchive size={18} />}
          Download all as ZIP
        </button>
      </div>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {sent !== null && !error && <p className="note-ok">Batch of {sent} queued. Follow it in the tray; the ZIP saves itself when it is done.</p>}
      <p className="fineprint">
        Every link is fetched at the highest quality it offers, video and audio merged, then packed into one ZIP. Links that fail are listed in
        <code>failed-links.txt</code> inside the archive; the rest still download.
      </p>
    </div>
  );
}
