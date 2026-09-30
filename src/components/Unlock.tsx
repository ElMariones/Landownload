import { useState } from 'react';
import { Lock, LoaderCircle, Server } from 'lucide-react';
import { api } from '../api';
import { HOSTED, loadConnection, normalizeServer, saveConnection } from '../lib/server';

/** Asks for the access key, plus the server address when the UI is hosted apart from the server. */
export function Unlock({ onUnlocked }: { onUnlocked: () => void }) {
  const [server, setServer] = useState(() => loadConnection().url);
  const [key, setKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const url = HOSTED ? normalizeServer(server) : '';
      const health = await api.health(url);
      let session = '';
      if (health.auth_required) {
        if (!key) throw new Error('This server needs its access key.');
        session = (await api.unlock(key, url)).session ?? '';
      }
      saveConnection({ url, session });
      onUnlocked();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not connect.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell unlock">
      <form onSubmit={submit} className="unlock-card">
        {HOSTED ? <Server size={26} /> : <Lock size={26} />}
        <h1>{HOSTED ? 'Connect your server' : 'Private workspace'}</h1>
        <p>
          {HOSTED
            ? 'Landownload downloads on your own server. Enter its address and the access key from its .env file. Both are remembered on this device.'
            : 'This Landownload server is protected. Enter the access key from its .env file.'}
        </p>
        {HOSTED && (
          <input
            type="url"
            inputMode="url"
            autoComplete="url"
            spellCheck={false}
            value={server}
            onChange={(e) => setServer(e.target.value)}
            placeholder="https://your-server.example.com"
            aria-label="Server address"
            autoFocus
          />
        )}
        <input
          type="password"
          autoComplete="current-password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="Access key"
          aria-label="Access key"
          autoFocus={!HOSTED}
        />
        {error && <p className="alert">{error}</p>}
        <button className="go wide" disabled={busy || (HOSTED ? !server.trim() : !key)}>
          {busy && <LoaderCircle className="spin" size={16} />} {HOSTED ? 'Connect' : 'Unlock'}
        </button>
      </form>
    </div>
  );
}
