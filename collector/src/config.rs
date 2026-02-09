use serde::Deserialize;
use std::path::Path;
use std::time::Duration;

#[derive(Deserialize)]
pub struct Config {
    pub defaults: Defaults,
    #[serde(default = "default_retention_days")]
    pub retention_days: u32,
    pub projects: Vec<Project>,
}

fn default_retention_days() -> u32 {
    90
}

#[derive(Deserialize)]
pub struct Defaults {
    pub interval_sec: u64,
    pub timeout_sec: u64,
    #[serde(default = "default_status_code")]
    pub expected_status_code: u16,
    #[serde(default = "default_http_method")]
    pub http_method: String,
}

fn default_status_code() -> u16 {
    200
}

fn default_http_method() -> String {
    "GET".to_string()
}

#[derive(Deserialize)]
pub struct Project {
    pub id: String,
    pub monitors: Vec<Monitor>,
}

#[derive(Deserialize)]
pub struct Monitor {
    pub site_key: String,
    pub url: String,
    pub interval_sec: Option<u64>,
    pub timeout_sec: Option<u64>,
    pub expected_status_code: Option<u16>,
    pub http_method: Option<String>,
}

pub struct ResolvedMonitor {
    pub project_id: String,
    pub site_key: String,
    pub url: String,
    pub interval: Duration,
    pub timeout: Duration,
    pub expected_status_code: u16,
    pub http_method: String,
}

impl Config {
    pub fn load(path: &Path) -> Config {
        let contents = std::fs::read_to_string(path)
            .unwrap_or_else(|e| panic!("failed to read config at {}: {e}", path.display()));
        serde_json::from_str(&contents)
            .unwrap_or_else(|e| panic!("failed to parse config at {}: {e}", path.display()))
    }

    pub fn resolve(self) -> Vec<ResolvedMonitor> {
        let mut resolved = Vec::new();
        for project in self.projects {
            for monitor in project.monitors {
                resolved.push(ResolvedMonitor {
                    project_id: project.id.clone(),
                    site_key: monitor.site_key,
                    url: monitor.url,
                    interval: Duration::from_secs(
                        monitor.interval_sec.unwrap_or(self.defaults.interval_sec),
                    ),
                    timeout: Duration::from_secs(
                        monitor.timeout_sec.unwrap_or(self.defaults.timeout_sec),
                    ),
                    expected_status_code: monitor
                        .expected_status_code
                        .unwrap_or(self.defaults.expected_status_code),
                    http_method: monitor
                        .http_method
                        .unwrap_or_else(|| self.defaults.http_method.clone()),
                });
            }
        }
        resolved
    }
}
