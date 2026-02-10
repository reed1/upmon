mod db;
mod env;
mod models;
mod server;

use tracing::info;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();

    let env = env::Env::load();

    let pool = db::init_pool(&env.database_url).await;
    info!("database ready");

    server::serve(pool, env.api_key, env.listen_port).await;
}
