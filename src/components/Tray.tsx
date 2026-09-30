import { useState } from 'react';
import { Check, ChevronDown, Download, FileArchive, LoaderCircle, Square, Trash2, TriangleAlert } from 'lucide-react';
import { api, type Job } from '../api';
import { formatBytes, formatEta, formatSpeed, timeAgo } from '../lib/format';
import { hostOf } from '../lib/links';

const ACTIVE = new Set(['queued', 'downloading', 'processing']);
const STATUS_TEXT: Record<Job['status'], string> = {
  queued: 'Waiting',
  downloading: 'Downloading',
  processing: 'Finishing',
  completed: 'Ready',
  failed: 'Failed',
  cancelled: 'Stopped',
};

interface Props {
  jobs: Job[];
  retentionHours?: number;
  onCancel: (id: string) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
}

export function Tray({ jobs, retentionHours, onCancel, onRemove, onClear }: Props) {
  const active = jobs.filter((j) => ACTIVE.has(j.status)).length;
  const finished = jobs.length - active;
  return (
    <aside className="tray" aria-label="Downloads">
      <header>
        <h2>
          The tray <span>{active ? `${active} running` : jobs.length ? `${jobs.length} saved` : 'empty'}</span>
        </h2>
        {finished > 0 && (
          <button className="text-btn" onClick={onClear}>
            Clear finished
          </button>
        )}
      </header>
      {jobs.length === 0 ? (
        <div className="tray-empty">
          <FileArchive size={28} />
          <p>Downloads land here with live progress. Files stay on this machine for {retentionHours ?? 48} hours, then clean themselves up.</p>
        </div>
      ) : (
        <ul>
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} onCancel={onCancel} onRemove={onRemove} />
          ))}
        </ul>
      )}
    </aside>
  );
}

function JobCard({ job, onCancel, onRemove }: { job: Job; onCancel: (id: string) => void; onRemove: (id: string) => void }) {
  const [open, setOpen] = useState(job.kind === 'batch' && ACTIVE.has(job.status));
  const running = ACTIVE.has(job.status);
  const progress = job.status === 'completed' ? 100 : job.progress ?? null;
  const items = job.items ?? [];
  const done = items.filter((i) => i.status === 'completed').length;
  const failed = items.filter((i) => i.status === 'failed').length;

  const facts = running
    ? [job.status === 'queued' ? 'in line' : '', formatSpeed(job.speed), formatEta(job.eta), job.kind === 'batch' ? `${done + failed}/${items.length}` : ''].filter(Boolean)
    : [formatBytes(job.size), job.kind === 'batch' && items.length ? `${done}/${items.length} saved` : '', timeAgo(job.created)].filter(Boolean);

  return (
    <li className={`job ${job.status}`}>
      <div className="job-head">
        <span className={`dot ${job.status}`} aria-hidden />
        <div className="job-title">
          <strong title={job.title}>
            {job.title}
          </strong>
          <span>
            {job.platform} · {job.quality} · {job.ext}
          </span>
        </div>
        <div className="job-actions">
          {running && (
            <button className="icon-btn" onClick={() => onCancel(job.id)} aria-label="Stop download" title="Stop">
              <Square size={14} />
            </button>
          )}
          {job.status === 'completed' && (
            <a className="icon-btn lit" href={api.fileUrl(job.id)} download={job.filename ?? undefined} aria-label="Save file" title="Save again">
              <Download size={15} />
            </a>
          )}
          {!running && (
            <button className="icon-btn" onClick={() => onRemove(job.id)} aria-label="Remove from tray and delete file" title="Remove">
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {(running || job.status === 'completed') && (
        <div className={`meter ${progress === null ? 'indeterminate' : ''} ${job.status}`} role="progressbar" aria-valuenow={progress ?? undefined} aria-valuemin={0} aria-valuemax={100}>
          <span style={{ width: `${progress ?? 100}%` }} />
        </div>
      )}

      <div className="job-foot">
        <span className={`state ${job.status}`}>{STATUS_TEXT[job.status]}</span>
        <span>{facts.join(' · ')}</span>
        {items.length > 0 && (
          <button className="text-btn" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? 'Hide' : 'Links'} <ChevronDown size={13} className={open ? 'flip' : ''} />
          </button>
        )}
      </div>
      {job.error && (
        <p className="job-error">
          <TriangleAlert size={13} /> {job.error}
        </p>
      )}

      {open && items.length > 0 && (
        <ol className="items">
          {items.map((item, index) => (
            <li key={index} className={item.status}>
              <span className="item-icon">
                {item.status === 'completed' ? <Check size={12} /> : item.status === 'failed' ? <TriangleAlert size={12} /> : item.status === 'downloading' ? <LoaderCircle size={12} className="spin" /> : index + 1}
              </span>
              <div>
                <span>{item.title ?? hostOf(item.url)}</span>
                {item.error && <em>{item.error}</em>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </li>
  );
}
