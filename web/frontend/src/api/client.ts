import type { Catalog, Dataset, Health, Job, Preset, ResultDetail, ResultEntry, RunRequest } from '../types';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options, headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map((item: { msg: string }) => item.msg).join(', ') : body.detail;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  catalog: () => request<Catalog>('/scripts'),
  dataset: () => request<Dataset>('/dataset'),
  presets: () => request<Preset[]>('/presets'),
  health: () => request<Health>('/health'),
  jobs: () => request<Job[]>('/jobs'),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  start: (body: RunRequest) => request<Job>('/jobs', { method: 'POST', body: JSON.stringify(body) }),
  preview: (body: RunRequest) => request<{ command: string; output: string | null }>('/jobs/preview', { method: 'POST', body: JSON.stringify(body) }),
  cancel: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: 'POST' }),
  logs: (id: string, source: string, offset: number) => request<{ text: string; offset: number }>(`/jobs/${id}/logs?${new URLSearchParams({ source, offset: String(offset) })}`),
  results: () => request<ResultEntry[]>('/results'),
  result: (id: string) => request<ResultDetail>(`/results/${id}`),
};

export function artifactUrl(path: string, download = false) {
  return `/api/artifacts?${new URLSearchParams({ path, download: String(download) })}`;
}
