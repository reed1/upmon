use chrono::Utc;
use reqwest::{Client, Method};
use std::time::Duration;
use tracing::warn;

use crate::config::ResolvedMonitor;
use crate::models::{CheckResult, ErrorType, truncate_error_message};

pub async fn execute_check(client: &Client, monitor: &ResolvedMonitor) -> CheckResult {
    let method = monitor.http_method.parse::<Method>().unwrap_or_else(|_| {
        panic!("invalid HTTP method '{}' for {}/{}", monitor.http_method, monitor.project_id, monitor.site_key)
    });

    let start = std::time::Instant::now();
    let result = client
        .request(method, &monitor.url)
        .timeout(monitor.timeout)
        .send()
        .await;
    let elapsed = start.elapsed();
    let response_ms = elapsed.as_millis().min(i32::MAX as u128) as i32;
    let checked_at = Utc::now();

    match result {
        Ok(response) => {
            let status = response.status().as_u16();
            let is_up = status == monitor.expected_status_code;

            let (error_type, error_message) = if is_up {
                (None, None)
            } else {
                let body = response.text().await.unwrap_or_default();
                warn!(
                    project = monitor.project_id,
                    site = monitor.site_key,
                    expected = monitor.expected_status_code,
                    actual = status,
                    "unexpected status code"
                );
                (Some(ErrorType::UnexpectedStatus), Some(truncate_error_message(&body)))
            };

            CheckResult {
                project_id: monitor.project_id.clone(),
                site_key: monitor.site_key.clone(),
                url: monitor.url.clone(),
                status_code: Some(status as i16),
                response_ms,
                is_up,
                error_type,
                error_message,
                checked_at,
            }
        }
        Err(e) => {
            let error_type = if e.is_timeout() {
                ErrorType::Timeout
            } else {
                ErrorType::ConnectionError
            };
            warn!(
                project = monitor.project_id,
                site = monitor.site_key,
                error_type = error_type.as_str(),
                error = %e,
                "check failed"
            );
            CheckResult {
                project_id: monitor.project_id.clone(),
                site_key: monitor.site_key.clone(),
                url: monitor.url.clone(),
                status_code: None,
                response_ms,
                is_up: false,
                error_type: Some(error_type),
                error_message: Some(e.to_string()),
                checked_at,
            }
        }
    }
}

pub fn build_client(timeout: Duration) -> Client {
    Client::builder()
        .timeout(timeout)
        .build()
        .expect("failed to build HTTP client")
}
