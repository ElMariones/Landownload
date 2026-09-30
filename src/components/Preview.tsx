import { useState } from 'react';
import { Download, Film, Image as ImageIcon, LoaderCircle, Music } from 'lucide-react';
import { assetUrl, type Media, type MediaOption, type OptionKind } from '../api';
import { formatBytes, formatDuration } from '../lib/format';

const GROUPS: { kind: OptionKind; title: string; icon: typeof Film }[] = [
  { kind: 'video', title: 'Video', icon: Film },
  { kind: 'image', title: 'Images', icon: ImageIcon },
  { kind: 'audio', title: 'Audio only', icon: Music },
];

interface Props {
  media: Media;
  pending: string | null;
  ffmpeg: boolean;
  onDownload: (optionId: string) => void;
}

export function Preview({ media, pending, ffmpeg, onDownload }: Props) {
  const [broken, setBroken] = useState(false);
  const top = media.options.find((o) => o.kind !== 'audio');

  return (
    <article className="preview">
      <div className="frame">
        {media.thumbnail && !broken ? (
          <img src={assetUrl(media.thumbnail)} alt="" onError={() => setBroken(true)} />
        ) : (
          <div className="frame-empty">
            <Film size={32} />
          </div>
        )}
        <div className="frame-tags">
          <span className="tag">{media.platform}</span>
          {media.count > 1 && <span className="tag">{media.count} files</span>}
        </div>
        {media.duration ? <span className="runtime">{formatDuration(media.duration)}</span> : null}
      </div>

      <div className="meta">
        <h2 title={media.title}>{media.title}</h2>
        <p className="byline">
          by <strong>{media.author}</strong>
        </p>
        {!ffmpeg && <p className="hint">FFmpeg is not installed, so some top resolutions download without sound. Install it to unlock merging and MP3.</p>}

        {GROUPS.map(({ kind, title, icon: Icon }) => {
          const options = media.options.filter((o) => o.kind === kind);
          if (!options.length) return null;
          return (
            <div className="menu" key={kind}>
              <h3>
                <Icon size={14} /> {title}
                <span>{options.length}</span>
              </h3>
              <ul>
                {options.map((option) => (
                  <OptionRow key={option.id} option={option} best={option === top} pending={pending} onDownload={onDownload} />
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function OptionRow({ option, best, pending, onDownload }: { option: MediaOption; best: boolean; pending: string | null; onDownload: (id: string) => void }) {
  const loading = pending === option.id;
  const details = [option.fps && option.fps > 30 ? `${option.fps} fps` : '', option.codec && option.kind !== 'image' ? option.codec : '', formatBytes(option.size)].filter(Boolean);
  return (
    <li className={best ? 'best' : ''}>
      <div className="opt-main">
        <span className="opt-label">{option.label}</span>
        <span className="ext">{option.ext}</span>
        {best && <span className="crown">top quality</span>}
        {option.kind === 'video' && option.audio === false && <span className="mute">no audio</span>}
      </div>
      <div className="opt-details">
        {details.join(' · ')}
        {option.note && <em>{option.note}</em>}
      </div>
      <button className="grab" onClick={() => onDownload(option.id)} disabled={pending !== null} aria-label={`Download ${option.label} ${option.ext}`}>
        {loading ? <LoaderCircle className="spin" size={16} /> : <Download size={16} />}
        <span>Save</span>
      </button>
    </li>
  );
}

export function PreviewPlaceholder({ loading }: { loading: boolean }) {
  if (loading) {
    return (
      <div className="preview skeleton" aria-busy>
        <div className="frame" />
        <div className="meta">
          <div className="bar w70" />
          <div className="bar w40" />
          <div className="bar" />
          <div className="bar" />
          <div className="bar w85" />
        </div>
      </div>
    );
  }
  return (
    <ol className="steps">
      <li>
        <b>01</b>
        <span>Paste a post, video, or image link.</span>
      </li>
      <li>
        <b>02</b>
        <span>Every quality the source offers is listed, up to the original upload.</span>
      </li>
      <li>
        <b>03</b>
        <span>Hit Save. The file lands in your downloads, clean.</span>
      </li>
    </ol>
  );
}
