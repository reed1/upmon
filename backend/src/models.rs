use chrono::{DateTime, Utc};

pub struct CheckResult {
    pub project_id: String,
    pub site_key: String,
    pub url: String,
    pub status_code: Option<i16>,
    pub response_ms: i32,
    pub is_up: bool,
    pub error: Option<String>,
    pub checked_at: DateTime<Utc>,
}
