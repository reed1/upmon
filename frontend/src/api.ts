import type {
  SiteStatus,
  DailySummaryResponse,
  AccessLogStats,
  AccessLogEntries,
  SiteSummary,
  FrontendErrorStats,
  FrontendErrorEntries,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

// The API key is issued by /pangolin/api-key (behind Pangolin SSO, which injects
// the remote-email identity). It's tied to the logged-in user; /api itself
// bypasses SSO and authenticates with this key. Fetched once and memoized.
let apiKeyPromise: Promise<string> | null = null;

function getApiKey(): Promise<string> {
  if (!apiKeyPromise) {
    apiKeyPromise = fetch(new URL('/pangolin/api-key', BASE_URL))
      .then(async (res) => {
        if (!res.ok) {
          apiKeyPromise = null;
          throw new Error(`Failed to obtain API key (${res.status})`);
        }
        return res.json();
      })
      .then((data) => data.api_key as string);
  }
  return apiKeyPromise;
}

async function api(
  path: string,
  params?: Record<string, string>,
): Promise<Response> {
  const url = new URL(path, BASE_URL);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      url.searchParams.set(k, v);
    }
  }
  const key = await getApiKey();
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${key}` },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res;
}

function siteUrl(
  base: string,
  projectId: string,
  siteKey: string,
  suffix: string,
): string {
  return `/api/v1/${base}/sites/${encodeURIComponent(projectId)}/${encodeURIComponent(siteKey)}/${suffix}`;
}

function setOptional(
  params: Record<string, string>,
  entries: Record<string, string | undefined>,
): Record<string, string> {
  for (const [k, v] of Object.entries(entries)) {
    if (v) params[k] = v;
  }
  return params;
}

export async function fetchStatus(projectId?: string): Promise<SiteStatus[]> {
  const res = await api(
    '/api/v1/status',
    projectId ? { project_id: projectId } : undefined,
  );
  return res.json();
}

export async function fetchDailySummary(
  projectId?: string,
  days?: number,
): Promise<DailySummaryResponse> {
  const params: Record<string, string> = {};
  if (projectId) params.project_id = projectId;
  if (days) params.days = String(days);
  const res = await api('/api/v1/daily-summary', params);
  return res.json();
}

export async function fetchAccessLogStats(
  projectId: string,
  siteKey: string,
  startTime: string,
  end?: string,
  exceptionType?: string,
  os?: string,
  clientType?: string,
  method?: string,
): Promise<AccessLogStats> {
  const params = setOptional(
    { start_time: startTime },
    {
      end,
      exception_type: exceptionType,
      os,
      client_type: clientType,
      method,
    },
  );
  const res = await api(
    siteUrl('access-logs', projectId, siteKey, 'stats'),
    params,
  );
  return res.json();
}

export async function fetchAccessLogEntries(
  projectId: string,
  siteKey: string,
  startTime: string,
  end?: string,
  exceptionType?: string,
  os?: string,
  clientType?: string,
  method?: string,
  orderBy?: string,
  orderDir?: string,
  limit?: number,
): Promise<AccessLogEntries> {
  const params = setOptional(
    { start_time: startTime },
    {
      end,
      exception_type: exceptionType,
      os,
      client_type: clientType,
      method,
      order_by: orderBy,
      order_dir: orderDir,
      limit: limit ? String(limit) : undefined,
    },
  );
  const res = await api(
    siteUrl('access-logs', projectId, siteKey, 'logs'),
    params,
  );
  return res.json();
}

// `next` is a server-built relative path carrying its own query string.
export async function fetchAccessLogPage(
  next: string,
): Promise<AccessLogEntries> {
  const res = await api(next);
  return res.json();
}

export async function fetchSiteSummary(
  projectId: string,
  siteKey: string,
): Promise<SiteSummary> {
  const res = await api(siteUrl('access-logs', projectId, siteKey, 'summary'));
  return res.json();
}

// Frontend errors carry more optional filters than access logs, so these take an
// options object rather than the positional style above.
export interface FrontendErrorFilters {
  end?: string;
  kind?: string;
  os?: string;
  clientType?: string;
  fingerprint?: string;
  sessionId?: string;
  orderBy?: string;
  orderDir?: string;
  limit?: number;
}

function frontendErrorParams(
  startTime: string,
  f: FrontendErrorFilters,
): Record<string, string> {
  return setOptional(
    { start_time: startTime },
    {
      end: f.end,
      kind: f.kind,
      os: f.os,
      client_type: f.clientType,
      fingerprint: f.fingerprint,
      session_id: f.sessionId,
      order_by: f.orderBy,
      order_dir: f.orderDir,
      limit: f.limit ? String(f.limit) : undefined,
    },
  );
}

export async function fetchFrontendErrorStats(
  projectId: string,
  siteKey: string,
  startTime: string,
  filters: FrontendErrorFilters = {},
): Promise<FrontendErrorStats> {
  const res = await api(
    siteUrl('frontend-errors', projectId, siteKey, 'stats'),
    frontendErrorParams(startTime, filters),
  );
  return res.json();
}

export async function fetchFrontendErrors(
  projectId: string,
  siteKey: string,
  startTime: string,
  filters: FrontendErrorFilters = {},
): Promise<FrontendErrorEntries> {
  const res = await api(
    siteUrl('frontend-errors', projectId, siteKey, 'logs'),
    frontendErrorParams(startTime, filters),
  );
  return res.json();
}

// `next` is a server-built relative path carrying its own query string.
export async function fetchFrontendErrorPage(
  next: string,
): Promise<FrontendErrorEntries> {
  const res = await api(next);
  return res.json();
}
