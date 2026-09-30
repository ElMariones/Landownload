import { clientId, HOSTED, loadConnection, SERVER_URL } from './lib/server';

export type OptionKind = 'video' | 'audio' | 'image';

export interface MediaOption {
  id: string;
  kind: OptionKind;
  label: string;
  ext: string;
  height?: number;
  fps?: number | null;
  size?: number | null;
  codec?: string | null;
  audio?: boolean;
  note?: string;
}

export interface Media {
  id: string;
  url: string;
  title: string;
  author: string;
  platform: string;
  duration: number | null;
  thumbnail: string | null;
  count: number;
  options: MediaOption[];
}

export type JobStatus = 'queued' | 'downloading' | 'processing' | 'completed' | 'failed' | 'cancelled';

export interface BatchItem {
  url: string;
  status: 'queued' | 'downloading' | 'completed' | 'failed';
  title: string | null;
  error: string | null;
}

export interface Job {
  id: string;
  title: string;
  platform: string;
  url: string;
  quality: string;
  kind: OptionKind | 'batch';
  ext: string;
  status: JobStatus;
  progress: number | null;
  speed: number | null;
  eta: number | null;
  created: number;
  size: number | null;
  filename: string | null;
  error: string | null;
  items?: BatchItem[];
}

export interface Health {
  status: string;
  ffmpeg: boolean;
  cookies: boolean;
  auth_required: boolean;
  engines: Record<string, string>;
  retention_hours: number;
  workers: number;
}

export interface Site {
  name: string;
  domain: string;
  category: 'video' | 'social' | 'image';
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

function base() {
  return HOSTED ? SERVER_URL || loadConnection().url : '';
}

/** For <img>/<a> requests, which cannot carry an Authorization header. */
export function assetUrl(path: string) {
  const { session } = loadConnection();
  return base() + path + (HOSTED && session ? `${path.includes('?') ? '&' : '?'}s=${encodeURIComponent(session)}` : '');
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }, server = base()): Promise<T> {
  const { json, ...rest } = init ?? {};
  const headers: Record<string, string> = { 'X-Client-Id': clientId() };
  if (json !== undefined) headers['Content-Type'] = 'application/json';
  const { session } = loadConnection();
  if (HOSTED && session) headers.Authorization = `Bearer ${session}`;
  let response: Response;
  try {
    response = await fetch(server + path, {
      // A switched-off server behind a tunnel can hang instead of refusing; give up quickly.
      signal: AbortSignal.timeout(path === '/api/inspect' || path === '/api/batches' ? 120_000 : 10_000),
      ...rest,
      credentials: HOSTED ? 'omit' : 'same-origin',
      headers,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    });
  } catch {
    throw new ApiError(HOSTED ? 'Could not reach your Landownload server. Is it running and is the address right?' : 'The Landownload server is not running. Start it with “python -m backend”.', 0);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
      else if (Array.isArray(body.detail)) message = 'That request was not valid. Check the links and try again.';
    } catch {
      /* Non-JSON error (proxy down, etc.) keeps the generic message. */
    }
    if (response.status === 502 || response.status === 504) message = 'The Landownload server is not responding.';
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: (server?: string) => request<Health>('/api/health', undefined, server),
  sites: () => request<Site[]>('/api/sites'),
  unlock: (token: string, server?: string) => request<{ ok: boolean; session?: string }>('/api/auth', { method: 'POST', json: { token } }, server),
  inspect: (url: string) => request<Media>('/api/inspect', { method: 'POST', json: { url } }),
  download: (mediaId: string, optionId: string) =>
    request<Job>('/api/downloads', { method: 'POST', json: { media_id: mediaId, option_id: optionId } }),
  batch: (urls: string[], mode: 'video' | 'audio') => request<Job>('/api/batches', { method: 'POST', json: { urls, mode } }),
  jobs: () => request<Job[]>('/api/downloads'),
  cancel: (id: string) => request<{ ok: boolean }>(`/api/downloads/${id}/cancel`, { method: 'POST', json: {} }),
  remove: (id: string) => request<{ ok: boolean }>(`/api/downloads/${id}`, { method: 'DELETE', json: {} }),
  fileUrl: (id: string) => assetUrl(`/api/downloads/${id}/file`),
};
