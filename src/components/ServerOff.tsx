import { useState } from 'react';
import { LoaderCircle, PowerOff } from 'lucide-react';

/** Shown while the server can't be reached; App keeps retrying in the background. */
export function ServerOff({ onRetry }: { onRetry: () => Promise<void> }) {
  const [checking, setChecking] = useState(false);

  async function retry() {
    setChecking(true);
    await onRetry();
    setChecking(false);
  }

  return (
    <div className="shell unlock">
      <div className="unlock-card off-card" role="status">
        <span className="off-icon">
          <PowerOff size={26} />
        </span>
        <h1>Server is off</h1>
        <p>The server has been turned off by the admin. This page reconnects by itself as soon as it's back on.</p>
        <button className="go wide" onClick={retry} disabled={checking}>
          {checking && <LoaderCircle className="spin" size={16} />} Check again
        </button>
      </div>
    </div>
  );
}
