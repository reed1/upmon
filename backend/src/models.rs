use chrono::{DateTime, NaiveDate, Utc};
use serde::Serialize;

#[derive(Serialize)]
pub struct MonitorStatus {
    pub project_id: String,
    pub site_key: String,
    pub url: String,
    pub status_code: Option<i16>,
    pub response_ms: i32,
    pub is_up: bool,
    pub error_type: Option<String>,
    pub error_message: Option<String>,
    pub last_checked_at: DateTime<Utc>,
    pub last_up_at: Option<DateTime<Utc>>,
}

#[derive(Serialize)]
pub struct DailySummary {
    pub project_id: String,
    pub site_key: String,
    pub day: NaiveDate,
    pub total_checks: i64,
    pub up_checks: i64,
    pub uptime_pct: f64,
}
