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
  minutes?: number,
  start?: string,
  end?: string,
): Promise<AccessLogStats> {
  const url = new URL(
    `/api/v1/access-logs/sites/${encodeURIComponent(projectId)}/${encodeURIComponent(siteKey)}/stats`,
    BASE_URL,
  );
  if (start && end) {
    url.searchParams.set('start', start);
    url.searchParams.set('end', end);
  } else if (minutes) {
    url.searchParams.set('minutes', String(minutes));
  }
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchAccessLogEntries(
  projectId: string,
  siteKey: string,
  minutes?: number,
  statusCode?: number,
  start?: string,
  end?: string,
): Promise<AccessLogEntries> {
  const url = new URL(
    `/api/v1/access-logs/sites/${encodeURIComponent(projectId)}/${encodeURIComponent(siteKey)}/logs`,
    BASE_URL,
  );
  if (start && end) {
    url.searchParams.set('start', start);
    url.searchParams.set('end', end);
  } else if (minutes) {
    url.searchParams.set('minutes', String(minutes));
  }
  if (statusCode != null)
    url.searchParams.set('status_code', String(statusCode));
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
