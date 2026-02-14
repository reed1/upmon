use std::sync::Arc;
use std::time::Duration;

use reqwest::Client;
use sqlx::PgPool;
use tokio::time::{self, MissedTickBehavior};
use tracing::{info, error};

use crate::config::ResolvedMonitor;
use crate::db;
use crate::monitor;

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

pub fn spawn_monitors(monitors: Vec<ResolvedMonitor>, pool: PgPool, client: Client) {
    let delays = stagger_delays(&monitors);

    for (m, initial_delay) in monitors.into_iter().zip(delays) {
        let pool = pool.clone();
        let client = client.clone();
        tokio::spawn(run_monitor_loop(Arc::new(m), pool, client, initial_delay));
    }
}

async fn run_monitor_loop(
    monitor: Arc<ResolvedMonitor>,
    pool: PgPool,
    client: Client,
    initial_delay: Duration,
) {
    if !initial_delay.is_zero() {
        info!(
            project = monitor.project_id,
            site = monitor.site_key,
            delay_ms = initial_delay.as_millis() as u64,
            "staggering start"
        );
        time::sleep(initial_delay).await;
    }

    let mut interval = time::interval(monitor.interval);
    interval.set_missed_tick_behavior(MissedTickBehavior::Delay);

    loop {
        interval.tick().await;

        info!(
            project = monitor.project_id,
            site = monitor.site_key,
            url = monitor.url,
            "checking"
        );

        let result = monitor::execute_check(&client, &monitor).await;

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
        // min_interval = 60s, step = 60/3 = 20s
        assert_eq!(delays, vec![
            Duration::ZERO,
            Duration::from_secs(20),
            Duration::from_secs(40),
        ]);
    }
}
