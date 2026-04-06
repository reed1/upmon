mod config;
mod db;
mod env;
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

    let env = env::Env::load();

    let config_path = Path::new("config.json");

    let config = config::Config::load(config_path);
    info!(retention_days = config.retention_days, "config loaded");

    let monitors = config.resolve();
    info!(count = monitors.len(), "monitors resolved");

    let pool = db::init_pool(&env.database_url).await;
    db::run_migrations(&pool).await;
    info!("database ready");

    let client = monitor::build_client(Duration::from_secs(30));
    let insecure_client = monitor::build_insecure_client(Duration::from_secs(30));

    let manager = scheduler::MonitorManager::new(pool, client, insecure_client);
    manager.start_initial(monitors);
    manager.watch_config(config_path).await;
}
