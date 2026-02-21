export interface SiteStatus {
  project_id: string;
  site_key: string;
  url: string;
  status_code: number;
  response_ms: number | null;
  is_up: boolean;
  error_type: string | null;
  error_message: string | null;
  last_checked_at: string;
  last_up_at: string | null;
}

export interface DayEntry {
  day: string;
  checks: (number | null)[];
}

export type DailySummaryResponse = Record<string, Record<string, DayEntry[]>>;

export interface AccessLogSiteInfo {
  project_id: string;
  site_key: string;
}

export interface AccessLogStats {
  summary: { columns: string[]; rows: any[][] };
  status_distribution: { columns: string[]; rows: any[][] };
}

export interface AccessLogEntries {
  columns: string[];
  rows: any[][];
}
