use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use chrono::{DateTime, Utc};
use serde::Serialize;

#[derive(Clone, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorType {
    Timeout,
    ConnectionError,
    UnexpectedStatus,
}

impl ErrorType {
    pub fn as_str(&self) -> &'static str {
        match self {
            ErrorType::Timeout => "timeout",
            ErrorType::ConnectionError => "connection_error",
            ErrorType::UnexpectedStatus => "unexpected_status",
        }
    }
}

#[derive(Clone, Serialize)]
pub struct CheckResult {
    pub project_id: String,
    pub site_key: String,
    pub url: String,
    pub status_code: Option<i16>,
    pub response_ms: i32,
    pub is_up: bool,
    pub error_type: Option<ErrorType>,
    pub error_message: Option<String>,
    pub checked_at: DateTime<Utc>,
}

pub type StatusCache = Arc<RwLock<HashMap<(String, String), CheckResult>>>;

const MAX_ERROR_CHARS: usize = 500;

pub fn truncate_error_message(body: &str) -> String {
    let char_count = body.chars().count();
    if char_count <= MAX_ERROR_CHARS {
        return body.to_string();
    }
    let truncated: String = body.chars().take(MAX_ERROR_CHARS).collect();
    format!("{truncated}... (truncated, {char_count} chars)")
}
