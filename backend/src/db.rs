use sqlx::PgPool;
use sqlx::postgres::PgPoolOptions;

use crate::models::CheckResult;

pub async fn init_pool(database_url: &str) -> PgPool {
    PgPoolOptions::new()
        .max_connections(5)
        .connect(database_url)
        .await
        .expect("failed to connect to database")
}

pub async fn run_migrations(pool: &PgPool) {
    sqlx::migrate!("./migrations")
        .run(pool)
        .await
        .expect("failed to run migrations");
}

pub async fn insert_check_result(pool: &PgPool, result: &CheckResult) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO monitor_checks (project_id, site_key, url, status_code, response_ms, is_up, error_type, error_message, checked_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
    )
    .bind(&result.project_id)
    .bind(&result.site_key)
    .bind(&result.url)
    .bind(result.status_code)
    .bind(result.response_ms)
    .bind(result.is_up)
    .bind(result.error_type.as_ref().map(|e| e.as_str()))
    .bind(&result.error_message)
    .bind(result.checked_at)
    .execute(pool)
    .await?;
    Ok(())
}
