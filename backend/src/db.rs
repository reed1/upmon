use std::collections::HashMap;

use chrono::Timelike;
use sqlx::PgPool;
use sqlx::postgres::PgPoolOptions;
use sqlx::Row;

use crate::models::{DayChecks, HourlySummary, MonitorStatus};

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

pub async fn get_hourly_summary(pool: &PgPool, project_id: Option<&str>, days: i32) -> Result<HourlySummary, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT project_id, site_key,
                time_bucket('1 hour', checked_at) AS hour,
                bool_and(is_up) AS all_up
         FROM monitor_checks
         WHERE checked_at > NOW() - make_interval(days => $1)
           AND ($2::text IS NULL OR project_id = $2)
         GROUP BY project_id, site_key, hour
         ORDER BY project_id, site_key, hour",
    )
    .bind(days)
    .bind(project_id)
    .fetch_all(pool)
    .await?;

    let mut result: HourlySummary = HashMap::new();

    for row in rows {
        let project_id: String = row.get("project_id");
        let site_key: String = row.get("site_key");
        let hour: chrono::DateTime<chrono::Utc> = row.get("hour");
        let all_up: bool = row.get("all_up");

        let date = hour.date_naive();
        let hour_idx = hour.hour() as usize;

        let days_vec = result
            .entry(project_id)
            .or_default()
            .entry(site_key)
            .or_default();

        let day_entry = match days_vec.last_mut() {
            Some(last) if last.day == date => last,
            _ => {
                days_vec.push(DayChecks {
                    day: date,
                    checks: vec![None; 24],
                });
                days_vec.last_mut().unwrap()
            }
        };

        day_entry.checks[hour_idx] = Some(if all_up { 1 } else { 0 });
    }

    Ok(result)
}
