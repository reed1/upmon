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

export interface SiteDailySummary {
  days: DayEntry[];
  cleanup_ok?: boolean;
  errors_ok?: boolean;
}

export type DailySummaryResponse = Record<
  string,
  Record<string, SiteDailySummary>
>;

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
  error_message: string | null;
}

export interface DailyErrorCount {
  date: string;
  error_count: number | null;
  agent_error: string | null;
}

export interface SiteSummary {
  cleanup_logs: CleanupLogEntry[];
  error_counts: DailyErrorCount[];
}
