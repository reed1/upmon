mod config;
mod db;
mod models;
mod monitor;
mod scheduler;

use std::path::Path;
use std::time::Duration;

use tracing::info;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();

    dotenvy::dotenv().ok();
    let database_url =
        std::env::var("DATABASE_URL").expect("DATABASE_URL must be set in .env or environment");

    let config = config::Config::load(Path::new("config.json"));
    info!(retention_days = config.retention_days, "config loaded");

    let monitors = config.resolve();
    info!(count = monitors.len(), "monitors resolved");

    let pool = db::init_pool(&database_url).await;
    db::run_migrations(&pool).await;
    info!("database ready");

    let client = monitor::build_client(Duration::from_secs(30));

    scheduler::spawn_monitors(monitors, pool, client);

    info!("upmon running — press ctrl+c to stop");
    tokio::signal::ctrl_c()
        .await
        .expect("failed to listen for ctrl+c");
    info!("shutting down");
}
