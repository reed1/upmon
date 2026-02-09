mod cache;
mod config;
mod db;
mod env;
mod models;
mod monitor;
mod scheduler;
mod server;

use std::path::Path;
use std::sync::{Arc, RwLock};
use std::time::Duration;

use tracing::info;
use tracing_subscriber::EnvFilter;

use crate::models::StatusCache;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();

    let env = env::Env::load();

    let config = config::Config::load(Path::new("config.json"));
    info!(retention_days = config.retention_days, "config loaded");

    let monitors = config.resolve();
    info!(count = monitors.len(), "monitors resolved");

    let pool = db::init_pool(&env.database_url).await;
    db::run_migrations(&pool).await;
    info!("database ready");

    let client = monitor::build_client(Duration::from_secs(30));

    let cache_path = Path::new("cache.json");
    let cache: StatusCache = Arc::new(RwLock::new(cache::load(cache_path)));

    scheduler::spawn_monitors(monitors, pool, client, cache.clone());
    tokio::spawn(server::serve(cache.clone(), env.api_key, env.api_port));

    let (shutdown_tx, mut shutdown_rx) = tokio::sync::oneshot::channel::<()>();
    let save_cache = cache.clone();
    let save_handle = tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(60));
        interval.tick().await;
        loop {
            tokio::select! {
                _ = interval.tick() => {}
                _ = &mut shutdown_rx => {
                    cache::save(cache_path, &save_cache);
                    break;
                }
            }
            cache::save(cache_path, &save_cache);
        }
    });

    info!("upmon running — press ctrl+c to stop");
    tokio::signal::ctrl_c()
        .await
        .expect("failed to listen for ctrl+c");
    info!("shutting down");

    let _ = shutdown_tx.send(());
    let _ = save_handle.await;
}
