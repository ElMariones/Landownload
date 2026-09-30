export function formatBytes(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return '';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const exp = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exp;
  return `${value >= 100 || exp === 0 ? Math.round(value) : value.toFixed(1)} ${units[exp]}`;
}

export function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds < 0) return '';
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rest = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${rest}` : `${m}:${rest}`;
}

export function formatSpeed(bytesPerSecond?: number | null): string {
  const size = formatBytes(bytesPerSecond);
  return size ? `${size}/s` : '';
}

export function formatEta(seconds?: number | null): string {
  if (seconds === null || seconds === undefined || seconds < 0) return '';
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))}s left`;
  return `${formatDuration(seconds)} left`;
}

export function timeAgo(epochSeconds: number): string {
  const diff = Date.now() / 1000 - epochSeconds;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return `${Math.floor(diff / 86400)} d ago`;
}
