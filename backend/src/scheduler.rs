use std::sync::Arc;
use std::time::Duration;

use reqwest::Client;
use sqlx::PgPool;
use tokio::time::{self, MissedTickBehavior};
use tracing::{info, error};

use crate::config::ResolvedMonitor;
use crate::db;
use crate::models::StatusCache;
use crate::monitor;

pub fn spawn_monitors(monitors: Vec<ResolvedMonitor>, pool: PgPool, client: Client, cache: StatusCache) {
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

    for (i, m) in monitors.into_iter().enumerate() {
        let pool = pool.clone();
        let client = client.clone();
        let cache = cache.clone();
        let initial_delay = stagger_step * i as u32;
        tokio::spawn(run_monitor_loop(Arc::new(m), pool, client, cache, initial_delay));
    }
}

async fn run_monitor_loop(
    monitor: Arc<ResolvedMonitor>,
    pool: PgPool,
    client: Client,
    cache: StatusCache,
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

        cache.write().unwrap().insert(
            (result.project_id.clone(), result.site_key.clone()),
            result.clone(),
        );

        if let Err(e) = db::insert_check_result(&pool, &result).await {
            error!(
                project = result.project_id,
                site = result.site_key,
                error = %e,
                "failed to insert check result"
            );
        }
    }
}
