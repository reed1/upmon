import type {
  SiteStatus,
  DailySummaryResponse,
  AccessLogSiteInfo,
  AccessLogStats,
  AccessLogEntries,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL;
const API_KEY = import.meta.env.VITE_API_KEY;

export async function fetchStatus(projectId?: string): Promise<SiteStatus[]> {
  const url = new URL('/api/v1/status', BASE_URL);
  if (projectId) url.searchParams.set('project_id', projectId);

  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });

  if (!res.ok) throw new Error(`API error: ${res.status}`);
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

  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchAccessLogSites(): Promise<AccessLogSiteInfo[]> {
  const url = new URL('/api/v1/access-logs/sites', BASE_URL);
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchAccessLogStats(
  projectId: string,
  siteKey: string,
  start: string,
  end?: string,
  statusCode?: number,
  method?: string,
): Promise<AccessLogStats> {
  const url = new URL(
    `/api/v1/access-logs/sites/${encodeURIComponent(projectId)}/${encodeURIComponent(siteKey)}/stats`,
    BASE_URL,
  );
  url.searchParams.set('start', start);
  if (end) url.searchParams.set('end', end);
  if (statusCode != null)
    url.searchParams.set('status_code', String(statusCode));
  if (method) url.searchParams.set('method', method);
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchAccessLogEntries(
  projectId: string,
  siteKey: string,
  start: string,
  statusCode?: number,
  end?: string,
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
  if (statusCode != null)
    url.searchParams.set('status_code', String(statusCode));
  if (method) url.searchParams.set('method', method);
  if (orderBy) url.searchParams.set('order_by', orderBy);
  if (orderDir) url.searchParams.set('order_dir', orderDir);
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
