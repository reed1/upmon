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
  configKey: string,
): Promise<AccessLogStats> {
  const url = new URL(
    `/api/v1/access-logs/sites/${encodeURIComponent(configKey)}/stats`,
    BASE_URL,
  );
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchAccessLogEntries(
  configKey: string,
  limit: number = 50,
): Promise<AccessLogEntries> {
  const url = new URL(
    `/api/v1/access-logs/sites/${encodeURIComponent(configKey)}/logs`,
    BASE_URL,
  );
  url.searchParams.set('limit', String(limit));
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
