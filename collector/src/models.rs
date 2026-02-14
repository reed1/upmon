use chrono::{DateTime, Utc};

#[derive(Clone)]
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

#[derive(Clone)]
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

const MAX_ERROR_CHARS: usize = 500;

pub fn truncate_error_message(body: &str) -> String {
    let char_count = body.chars().count();
    if char_count <= MAX_ERROR_CHARS {
        return body.to_string();
    }
    let truncated: String = body.chars().take(MAX_ERROR_CHARS).collect();
    format!("{truncated}... (truncated, {char_count} chars)")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn truncate_under_limit_is_noop() {
        let input = "short error";
        assert_eq!(truncate_error_message(input), input);
    }

    #[test]
    fn truncate_exactly_at_limit() {
        let input: String = "a".repeat(MAX_ERROR_CHARS);
        assert_eq!(truncate_error_message(&input), input);
    }

    #[test]
    fn truncate_over_limit() {
        let input: String = "b".repeat(MAX_ERROR_CHARS + 50);
        let result = truncate_error_message(&input);
        assert!(result.starts_with(&"b".repeat(MAX_ERROR_CHARS)));
        assert!(result.contains("... (truncated, 550 chars)"));
    }

    #[test]
    fn truncate_multibyte_utf8() {
        // Each emoji is multiple bytes but one char
        let input: String = "\u{1F600}".repeat(MAX_ERROR_CHARS + 10);
        let result = truncate_error_message(&input);
        let prefix: String = "\u{1F600}".repeat(MAX_ERROR_CHARS);
        assert!(result.starts_with(&prefix));
        assert!(result.contains("510 chars"));
    }

    #[test]
    fn error_type_as_str() {
        assert_eq!(ErrorType::Timeout.as_str(), "timeout");
        assert_eq!(ErrorType::ConnectionError.as_str(), "connection_error");
        assert_eq!(ErrorType::UnexpectedStatus.as_str(), "unexpected_status");
    }
}
