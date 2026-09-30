/** Where the API lives. The bundled UI talks to its own origin; the hosted (GitHub Pages) build asks for a server. */
export const HOSTED = import.meta.env.VITE_HOSTED === '1';

export interface Connection {
  url: string;
  session: string;
}

const KEY = 'landownload:connection';

export function loadConnection(): Connection {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    if (saved && typeof saved.url === 'string' && typeof saved.session === 'string') return saved;
  } catch {
    /* Blocked or corrupt storage: fall through to an empty connection. */
  }
  return { url: '', session: '' };
}

export function saveConnection(connection: Connection) {
  try {
    localStorage.setItem(KEY, JSON.stringify(connection));
  } catch {
    /* Private windows can refuse storage; the connection still works until reload. */
  }
}

export function normalizeServer(input: string): string {
  let value = input.trim().replace(/\/+$/, '');
  if (value && !/^https?:\/\//i.test(value)) value = `https://${value}`;
  return value;
}
