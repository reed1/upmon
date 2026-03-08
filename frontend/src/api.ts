import type {
  SiteStatus,
  DailySummaryResponse,
  AccessLogSiteInfo,
  AccessLogStats,
  AccessLogEntries,
  CleanupLogEntry,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL;
const API_KEY = import.meta.env.VITE_API_KEY;

async function throwApiError(res: Response): Promise<never> {
  const body = await res.text();
  throw new Error(`API error ${res.status}: ${body}`);
}

export async function fetchStatus(projectId?: string): Promise<SiteStatus[]> {
  const url = new URL('/api/v1/status', BASE_URL);
  if (projectId) url.searchParams.set('project_id', projectId);

  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });

  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function fetchDailySummary(
  projectId?: string,
  days?: number,
): Promise<DailySummaryResponse> {
  const url = new URL('/api/v1/daily-summary', BASE_URL);
  if (projectId) url.searchParams.set('project_id', projectId);
  if (days) url.searchParams.set('days', String(days));

  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });

  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function fetchAccessLogSites(): Promise<AccessLogSiteInfo[]> {
  const url = new URL('/api/v1/access-logs/sites', BASE_URL);
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function fetchAccessLogStats(
  projectId: string,
  siteKey: string,
  start: string,
  end?: string,
  exceptionType?: string,
  os?: string,
  clientType?: string,
  method?: string,
): Promise<AccessLogStats> {
  const url = new URL(
    `/api/v1/access-logs/sites/${encodeURIComponent(projectId)}/${encodeURIComponent(siteKey)}/stats`,
    BASE_URL,
  );
  url.searchParams.set('start', start);
  if (end) url.searchParams.set('end', end);
  if (exceptionType) url.searchParams.set('exception_type', exceptionType);
  if (os) url.searchParams.set('os', os);
  if (clientType) url.searchParams.set('client_type', clientType);
  if (method) url.searchParams.set('method', method);
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function fetchAccessLogEntries(
  projectId: string,
  siteKey: string,
  start: string,
  end?: string,
  exceptionType?: string,
  os?: string,
  clientType?: string,
  method?: string,
  orderBy?: string,
  orderDir?: string,
): Promise<AccessLogEntries> {
  const url = new URL(
    `/api/v1/access-logs/sites/${encodeURIComponent(projectId)}/${encodeURIComponent(siteKey)}/logs`,
    BASE_URL,
  );
  url.searchParams.set('start', start);
  if (end) url.searchParams.set('end', end);
  if (exceptionType) url.searchParams.set('exception_type', exceptionType);
  if (os) url.searchParams.set('os', os);
  if (clientType) url.searchParams.set('client_type', clientType);
  if (method) url.searchParams.set('method', method);
  if (orderBy) url.searchParams.set('order_by', orderBy);
  if (orderDir) url.searchParams.set('order_dir', orderDir);
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function fetchCleanupLogs(
  projectId: string,
  siteKey: string,
  limit = 5,
): Promise<CleanupLogEntry[]> {
  const url = new URL(
    `/api/v1/access-logs/sites/${encodeURIComponent(projectId)}/${encodeURIComponent(siteKey)}/cleanup-logs`,
    BASE_URL,
  );
  url.searchParams.set('limit', String(limit));
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
}
