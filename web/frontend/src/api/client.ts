import type {
  Catalog,
  Dataset,
  Health,
  Job,
  Preset,
  ResponseLogEntry,
  ResultDetail,
  ResultEntry,
  RunRequest,
} from '../types';

interface PreviewResult {
  command: string;
  output: string | null;
}

interface LogChunk {
  text: string;
  offset: number;
}

interface ResponseLogFilters {
  q: string;
  errors_only: boolean;
  method: string;
}

interface ResponseLogs {
  folder: string;
  entries: ResponseLogEntry[];
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));

    let detail = body.detail;

    if (Array.isArray(body.detail)) {
      detail = body.detail
        .map((item: { msg: string }) => item.msg)
        .join(', ');
    }

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
  start: (body: RunRequest) => (
    request<Job>('/jobs', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  ),
  preview: (body: RunRequest) => (
    request<PreviewResult>('/jobs/preview', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  ),
  cancel: (id: string) => (
    request<Job>(`/jobs/${id}/cancel`, { method: 'POST' })
  ),
  logs: (id: string, source: string, offset: number) => {
    const query = new URLSearchParams({
      source,
      offset: String(offset),
    });

    return request<LogChunk>(`/jobs/${id}/logs?${query}`);
  },
  results: () => request<ResultEntry[]>('/results'),
  result: (id: string) => request<ResultDetail>(`/results/${id}`),
  responseLogs: (filters: ResponseLogFilters) => {
    const query = new URLSearchParams({
      limit: '200',
      q: filters.q,
      errors_only: String(filters.errors_only),
      method: filters.method,
    });

    return request<ResponseLogs>(`/response-logs?${query}`);
  },
};

export function artifactUrl(path: string, download = false) {
  const query = new URLSearchParams({
    path,
    download: String(download),
  });

  return `/api/artifacts?${query}`;
}
