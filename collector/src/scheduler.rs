use std::collections::HashMap;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use notify::{Watcher, RecursiveMode, recommended_watcher};
use reqwest::Client;
use sqlx::PgPool;
use tokio::sync::mpsc;
use tokio::time;
use tracing::{info, error};

use crate::config::{self, MonitorKey, ResolvedMonitor};
use crate::db;
use crate::monitor;

type MonitorMap = Arc<Mutex<HashMap<MonitorKey, Arc<ResolvedMonitor>>>>;

pub struct MonitorManager {
    monitors: MonitorMap,
    pool: PgPool,
    client: Client,
    insecure_client: Client,
}

impl MonitorManager {
    pub fn new(pool: PgPool, client: Client, insecure_client: Client) -> Self {
        Self {
            monitors: Arc::new(Mutex::new(HashMap::new())),
            pool,
            client,
            insecure_client,
        }
    }

    pub fn start_initial(&self, monitors: Vec<ResolvedMonitor>) {
        let delays = stagger_delays(&monitors);
        let mut map = self.monitors.lock().unwrap();
        for (m, delay) in monitors.into_iter().zip(delays) {
            let key = m.key();
            map.insert(key.clone(), Arc::new(m));
            self.spawn_loop(key, delay);
        }
    }

    pub fn reload(&self, new_monitors: Vec<ResolvedMonitor>) {
        let new_map: HashMap<MonitorKey, ResolvedMonitor> = new_monitors
            .into_iter()
            .map(|m| (m.key(), m))
            .collect();

        let mut map = self.monitors.lock().unwrap();

        let removed: Vec<MonitorKey> = map.keys()
            .filter(|k| !new_map.contains_key(k))
            .cloned()
            .collect();
        for key in &removed {
            info!(project = %key.0, site = %key.1, "removing monitor");
            map.remove(key);
        }

        for (key, monitor) in new_map {
            match map.get(&key) {
                Some(existing) if existing.as_ref() == &monitor => {}
                Some(_) => {
                    info!(project = %key.0, site = %key.1, "updating monitor config");
                    map.insert(key, Arc::new(monitor));
                }
                None => {
                    info!(project = %key.0, site = %key.1, "starting new monitor");
                    map.insert(key.clone(), Arc::new(monitor));
                    self.spawn_loop(key, Duration::ZERO);
                }
            }
        }
    }

    fn spawn_loop(&self, key: MonitorKey, initial_delay: Duration) {
        tokio::spawn(run_monitor_loop(
            key,
            self.monitors.clone(),
            self.pool.clone(),
            self.client.clone(),
            self.insecure_client.clone(),
            initial_delay,
        ));
    }

    pub async fn watch_config(&self, config_path: &Path) {
        let (tx, mut rx) = mpsc::channel::<()>(16);
        let _watcher = {
            let mut w = recommended_watcher(move |res: Result<notify::Event, notify::Error>| {
                if res.is_ok() {
                    let _ = tx.blocking_send(());
                }
            })
            .expect("failed to create file watcher");
            w.watch(config_path, RecursiveMode::NonRecursive)
                .expect("failed to watch config.json");
            w
        };

        info!("collector running — watching config.json for changes");

        loop {
            tokio::select! {
                _ = tokio::signal::ctrl_c() => {
                    info!("shutting down");
                    break;
                }
                Some(()) = rx.recv() => {
                    time::sleep(Duration::from_millis(500)).await;
                    while rx.try_recv().is_ok() {}

                    info!("config.json changed, reloading");
                    let new_config = config::Config::load(config_path);
                    info!(retention_days = new_config.retention_days, "new config parsed");
                    let new_monitors = new_config.resolve();
                    info!(count = new_monitors.len(), "new monitors resolved");
                    self.reload(new_monitors);
                    info!("config reload complete");
                }
            }
        }
    }
}

pub fn stagger_delays(monitors: &[ResolvedMonitor]) -> Vec<Duration> {
    let count = monitors.len();
    let min_interval = monitors
        .iter()
        .map(|m| m.interval)
        .min()
        .unwrap_or(Duration::from_secs(120));
    let stagger_step = if count > 1 {
        min_interval / count as u32
    } else {
        Duration::ZERO
    };
    (0..count)
        .map(|i| stagger_step * i as u32)
        .collect()
}

async fn run_monitor_loop(
    key: MonitorKey,
    monitors: MonitorMap,
    pool: PgPool,
    client: Client,
    insecure_client: Client,
    initial_delay: Duration,
) {
    if !initial_delay.is_zero() {
        info!(
            project = %key.0,
            site = %key.1,
            delay_ms = initial_delay.as_millis() as u64,
            "staggering start"
        );
        time::sleep(initial_delay).await;
    }

    loop {
        let Some(monitor) = monitors.lock().unwrap().get(&key).cloned() else {
            info!(project = %key.0, site = %key.1, "monitor removed, stopping");
            return;
        };

        let selected_client = if monitor.tls_skip_verify {
            &insecure_client
        } else {
            &client
        };

        info!(
            project = monitor.project_id,
            site = monitor.site_key,
            url = monitor.url,
            "checking"
        );

        let result = monitor::execute_check(selected_client, &monitor).await;

        info!(
            project = result.project_id,
            site = result.site_key,
            is_up = result.is_up,
            status_code = result.status_code,
            response_ms = result.response_ms,
            "check complete"
        );

        if let Err(e) = db::insert_check_result(&pool, &result).await {
            error!(
                project = result.project_id,
                site = result.site_key,
                error = %e,
                "failed to insert check result"
            );
        }

        if let Err(e) = db::upsert_monitor_status(&pool, &result).await {
            error!(
                project = result.project_id,
                site = result.site_key,
                error = %e,
                "failed to upsert monitor status"
            );
        }

        time::sleep(monitor.interval).await;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_monitor(interval_secs: u64) -> ResolvedMonitor {
        ResolvedMonitor {
            project_id: "p".into(),
            site_key: "s".into(),
            url: "http://example.com".into(),
            interval: Duration::from_secs(interval_secs),
            timeout: Duration::from_secs(10),
            expected_status_code: 200,
            http_method: "GET".into(),
            expected_body: None,
            tls_skip_verify: false,
        }
    }

    #[test]
    fn single_monitor_zero_delay() {
        let monitors = vec![make_monitor(120)];
        let delays = stagger_delays(&monitors);
        assert_eq!(delays, vec![Duration::ZERO]);
    }

    #[test]
    fn two_monitors_evenly_spaced() {
        let monitors = vec![make_monitor(120), make_monitor(120)];
        let delays = stagger_delays(&monitors);
        assert_eq!(delays, vec![Duration::ZERO, Duration::from_secs(60)]);
    }

    #[test]
    fn three_monitors_uses_min_interval() {
        let monitors = vec![
            make_monitor(300),
            make_monitor(60),
            make_monitor(120),
        ];
        let delays = stagger_delays(&monitors);
        assert_eq!(delays, vec![
            Duration::ZERO,
            Duration::from_secs(20),
            Duration::from_secs(40),
        ]);
    }
}
