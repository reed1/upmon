use sqlx::PgPool;
use sqlx::postgres::PgPoolOptions;
use sqlx::Row;

use crate::models::MonitorStatus;

pub async fn init_pool(database_url: &str) -> PgPool {
    PgPoolOptions::new()
        .max_connections(5)
        .connect(database_url)
        .await
        .expect("failed to connect to database")
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
