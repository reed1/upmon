use sqlx::PgPool;
use sqlx::postgres::PgPoolOptions;
use sqlx::Row;

use crate::models::{CheckResult, MonitorStatus};

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

pub async fn upsert_monitor_status(pool: &PgPool, result: &CheckResult) -> Result<(), sqlx::Error> {
    let last_up_at = if result.is_up { Some(result.checked_at) } else { None };

    sqlx::query(
        "INSERT INTO monitor_status (project_id, site_key, url, status_code, response_ms, is_up, error_type, error_message, last_checked_at, last_up_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
         ON CONFLICT (project_id, site_key) DO UPDATE SET
           url = EXCLUDED.url,
           status_code = EXCLUDED.status_code,
           response_ms = EXCLUDED.response_ms,
           is_up = EXCLUDED.is_up,
           error_type = EXCLUDED.error_type,
           error_message = EXCLUDED.error_message,
           last_checked_at = EXCLUDED.last_checked_at,
           last_up_at = CASE WHEN EXCLUDED.is_up THEN EXCLUDED.last_checked_at
                        ELSE monitor_status.last_up_at END",
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
    .bind(last_up_at)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn get_monitor_statuses(pool: &PgPool, project_id: Option<&str>) -> Result<Vec<MonitorStatus>, sqlx::Error> {
    let rows = match project_id {
        Some(pid) => {
            sqlx::query(
                "SELECT project_id, site_key, url, status_code, response_ms, is_up, error_type, error_message, last_checked_at, last_up_at
                 FROM monitor_status
                 WHERE project_id = $1
                 ORDER BY project_id, site_key",
            )
            .bind(pid)
            .fetch_all(pool)
            .await?
        }
        None => {
            sqlx::query(
                "SELECT project_id, site_key, url, status_code, response_ms, is_up, error_type, error_message, last_checked_at, last_up_at
                 FROM monitor_status
                 ORDER BY project_id, site_key",
            )
            .fetch_all(pool)
            .await?
        }
    };

    let statuses = rows
        .into_iter()
        .map(|row| MonitorStatus {
            project_id: row.get("project_id"),
            site_key: row.get("site_key"),
            url: row.get("url"),
            status_code: row.get("status_code"),
            response_ms: row.get("response_ms"),
            is_up: row.get("is_up"),
            error_type: row.get("error_type"),
            error_message: row.get("error_message"),
            last_checked_at: row.get("last_checked_at"),
            last_up_at: row.get("last_up_at"),
        })
        .collect();

    Ok(statuses)
}
