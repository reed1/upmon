use sqlx::PgPool;
use sqlx::postgres::PgPoolOptions;
use sqlx::Row;

use crate::models::{DailySummary, MonitorStatus};

pub async fn init_pool(database_url: &str) -> PgPool {
    PgPoolOptions::new()
        .max_connections(5)
        .connect(database_url)
        .await
        .expect("failed to connect to database")
}

pub async fn get_monitor_statuses(pool: &PgPool, project_id: Option<&str>) -> Result<Vec<MonitorStatus>, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT project_id, site_key, url, status_code, response_ms, is_up, error_type, error_message, last_checked_at, last_up_at
         FROM monitor_status
         WHERE ($1::text IS NULL OR project_id = $1)
         ORDER BY project_id, site_key",
    )
    .bind(project_id)
    .fetch_all(pool)
    .await?;

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

pub async fn get_daily_summary(pool: &PgPool, project_id: Option<&str>, days: i32) -> Result<Vec<DailySummary>, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT project_id, site_key,
                time_bucket('1 day', checked_at)::date AS day,
                COUNT(*)::bigint AS total_checks,
                COUNT(*) FILTER (WHERE is_up)::bigint AS up_checks
         FROM monitor_checks
         WHERE checked_at > NOW() - make_interval(days => $1)
           AND ($2::text IS NULL OR project_id = $2)
         GROUP BY project_id, site_key, day
         ORDER BY project_id, site_key, day",
    )
    .bind(days)
    .bind(project_id)
    .fetch_all(pool)
    .await?;

    let summaries = rows
        .into_iter()
        .map(|row| {
            let total_checks: i64 = row.get("total_checks");
            let up_checks: i64 = row.get("up_checks");
            let uptime_pct = if total_checks > 0 {
                (up_checks as f64 / total_checks as f64) * 100.0
            } else {
                0.0
            };
            DailySummary {
                project_id: row.get("project_id"),
                site_key: row.get("site_key"),
                day: row.get("day"),
                total_checks,
                up_checks,
                uptime_pct,
            }
        })
        .collect();

    Ok(summaries)
}
