import type {
  SiteStatus,
  DailySummaryResponse,
  AccessLogSiteInfo,
  AccessLogStats,
  AccessLogEntries,
  SiteSummary,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL;
const API_KEY = import.meta.env.VITE_API_KEY;

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
  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res;
}

function siteUrl(projectId: string, siteKey: string, suffix: string): string {
  return `/api/v1/access-logs/sites/${encodeURIComponent(projectId)}/${encodeURIComponent(siteKey)}/${suffix}`;
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

export async function fetchAccessLogSites(): Promise<AccessLogSiteInfo[]> {
  const res = await api('/api/v1/access-logs/sites');
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
  const params = setOptional(
    { start },
    {
      end,
      exception_type: exceptionType,
      os,
      client_type: clientType,
      method,
    },
  );
  const res = await api(siteUrl(projectId, siteKey, 'stats'), params);
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
  const params = setOptional(
    { start },
    {
      end,
      exception_type: exceptionType,
      os,
      client_type: clientType,
      method,
      order_by: orderBy,
      order_dir: orderDir,
    },
  );
  const res = await api(siteUrl(projectId, siteKey, 'logs'), params);
  return res.json();
}

export async function fetchSiteSummary(
  projectId: string,
  siteKey: string,
): Promise<SiteSummary> {
  const res = await api(siteUrl(projectId, siteKey, 'summary'));
  return res.json();
}
