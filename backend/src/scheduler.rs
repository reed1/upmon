use std::sync::Arc;

use reqwest::Client;
use sqlx::PgPool;
use tokio::time::{self, MissedTickBehavior};
use tracing::{info, error};

use crate::config::ResolvedMonitor;
use crate::db;
use crate::monitor;

pub fn spawn_monitors(monitors: Vec<ResolvedMonitor>, pool: PgPool, client: Client) {
    for m in monitors {
        let pool = pool.clone();
        let client = client.clone();
        tokio::spawn(run_monitor_loop(Arc::new(m), pool, client));
    }
}

async fn run_monitor_loop(monitor: Arc<ResolvedMonitor>, pool: PgPool, client: Client) {
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
    }
}
