use std::collections::HashMap;

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
pub struct DayChecks {
    pub day: NaiveDate,
    pub checks: Vec<Option<u8>>,
}

pub type HourlySummary = HashMap<String, HashMap<String, Vec<DayChecks>>>;
