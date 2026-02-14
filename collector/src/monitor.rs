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
        Ok(mut response) => {
            let status = response.status().as_u16();
            let is_up = status == monitor.expected_status_code;

            let (error_type, error_message) = if is_up {
                (None, None)
            } else {
                const MAX_BODY_BYTES: usize = 2048;
                let mut buf = Vec::with_capacity(MAX_BODY_BYTES);
                while let Ok(Some(chunk)) = response.chunk().await {
                    let remaining = MAX_BODY_BYTES - buf.len();
                    buf.extend_from_slice(&chunk[..chunk.len().min(remaining)]);
                    if buf.len() >= MAX_BODY_BYTES {
                        break;
                    }
                }
                let body = String::from_utf8_lossy(&buf);
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

#[cfg(test)]
mod tests {
    use super::*;
    use wiremock::matchers::{method, path};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    fn make_monitor(url: &str) -> ResolvedMonitor {
        ResolvedMonitor {
            project_id: "test-proj".into(),
            site_key: "test-site".into(),
            url: url.to_string(),
            interval: Duration::from_secs(60),
            timeout: Duration::from_secs(5),
            expected_status_code: 200,
            http_method: "GET".into(),
        }
    }

    #[tokio::test]
    async fn check_200_ok() {
        let server = MockServer::start().await;
        Mock::given(method("GET"))
            .and(path("/health"))
            .respond_with(ResponseTemplate::new(200))
            .mount(&server)
            .await;

        let client = Client::new();
        let monitor = make_monitor(&format!("{}/health", server.uri()));
        let result = execute_check(&client, &monitor).await;

        assert!(result.is_up);
        assert_eq!(result.status_code, Some(200));
        assert!(result.error_type.is_none());
        assert!(result.error_message.is_none());
    }

    #[tokio::test]
    async fn check_404_unexpected_status() {
        let server = MockServer::start().await;
        Mock::given(method("GET"))
            .and(path("/missing"))
            .respond_with(ResponseTemplate::new(404).set_body_string("not found"))
            .mount(&server)
            .await;

        let client = Client::new();
        let monitor = make_monitor(&format!("{}/missing", server.uri()));
        let result = execute_check(&client, &monitor).await;

        assert!(!result.is_up);
        assert_eq!(result.status_code, Some(404));
        assert_eq!(result.error_type.as_ref().unwrap().as_str(), "unexpected_status");
        assert!(result.error_message.as_ref().unwrap().contains("not found"));
    }

    #[tokio::test]
    async fn check_connection_refused() {
        let client = Client::new();
        let monitor = make_monitor("http://127.0.0.1:1");
        let result = execute_check(&client, &monitor).await;

        assert!(!result.is_up);
        assert!(result.status_code.is_none());
        assert_eq!(result.error_type.as_ref().unwrap().as_str(), "connection_error");
    }
}
