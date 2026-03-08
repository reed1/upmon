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
  exception_distribution: { columns: string[]; rows: any[][] };
  method_distribution: { columns: string[]; rows: any[][] };
  os_distribution: { columns: string[]; rows: any[][] };
  client_type_distribution: { columns: string[]; rows: any[][] };
  volume: { columns: string[]; rows: any[][] };
}

export interface AccessLogEntries {
  columns: string[];
  rows: any[][];
}

export interface CleanupLogEntry {
  id: number;
  executed_at: string;
  retention_days: number;
  status_code: number | null;
  deleted_count: number | null;
  duration_ms: number;
  error: string | null;
}
