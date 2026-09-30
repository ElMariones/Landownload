import { Server } from 'lucide-react';
import type { Health } from '../api';

interface Props {
  health: Health | null;
  offline: boolean;
  onChangeServer?: () => void;
}

export function Masthead({ health, offline, onChangeServer }: Props) {
  return (
    <header className="masthead">
      <div className="brand">
        <span className="brand-mark" aria-hidden>
          <svg viewBox="0 0 64 64">
            <path d="M32 13v27m-11-11 11 11 11-11M16 43v9h32v-9" />
          </svg>
        </span>
        <div>
          <h1>
            Lan<span>download</span>
          </h1>
          <p className="tagline">No ads. No quality caps. No nonsense. Paste a link, keep the file.</p>
        </div>
      </div>

      <div className="status-strip">
        {offline ? (
          <span className="pill bad">
            <i /> Server offline
          </span>
        ) : health ? (
          <>
            <span className="pill ok" title="Your Landownload server is reachable">
              <i /> Online
            </span>
            <span className={`pill ${health.ffmpeg ? 'ok' : 'warn'}`} title={health.ffmpeg ? 'FFmpeg found: merging and MP3 enabled' : 'Install FFmpeg to merge best video + audio'}>
              <i /> FFmpeg
            </span>
            <span className="pill quiet" title="yt-dlp engine version">
              yt-dlp {health.engines['yt-dlp']}
            </span>
            {health.cookies && <span className="pill quiet">cookies on</span>}
          </>
        ) : (
          <span className="pill quiet">connecting…</span>
        )}
        {onChangeServer && (
          <button className="server-btn" onClick={onChangeServer} title="Connect to a different server">
            <Server size={14} /> Server
          </button>
        )}
      </div>
    </header>
  );
}
