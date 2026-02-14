use std::collections::HashMap;

use chrono::{DateTime, Timelike, Utc};
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

pub struct HourlyRow {
    pub project_id: String,
    pub site_key: String,
    pub hour: DateTime<Utc>,
    pub all_up: bool,
}

pub fn build_hourly_summary(rows: Vec<HourlyRow>) -> HourlySummary {
    let mut result: HourlySummary = HashMap::new();

    for row in rows {
        let date = row.hour.date_naive();
        let hour_idx = row.hour.hour() as usize;

        let days_vec = result
            .entry(row.project_id)
            .or_default()
            .entry(row.site_key)
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

        day_entry.checks[hour_idx] = Some(if row.all_up { 1 } else { 0 });
    }

    result
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

    let hourly_rows: Vec<HourlyRow> = rows
        .into_iter()
        .map(|row| HourlyRow {
            project_id: row.get("project_id"),
            site_key: row.get("site_key"),
            hour: row.get("hour"),
            all_up: row.get("all_up"),
        })
        .collect();

    Ok(build_hourly_summary(hourly_rows))
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::NaiveDate;

    fn make_row(project: &str, site: &str, hour_str: &str, all_up: bool) -> HourlyRow {
        HourlyRow {
            project_id: project.into(),
            site_key: site.into(),
            hour: hour_str.parse::<DateTime<Utc>>().unwrap(),
            all_up,
        }
    }

    #[test]
    fn empty_rows_empty_result() {
        let result = build_hourly_summary(vec![]);
        assert!(result.is_empty());
    }

    #[test]
    fn single_project_single_day() {
        let rows = vec![
            make_row("p1", "s1", "2025-01-15T00:00:00Z", true),
            make_row("p1", "s1", "2025-01-15T01:00:00Z", false),
            make_row("p1", "s1", "2025-01-15T05:00:00Z", true),
        ];
        let result = build_hourly_summary(rows);
        let days = &result["p1"]["s1"];
        assert_eq!(days.len(), 1);
        assert_eq!(days[0].day, NaiveDate::from_ymd_opt(2025, 1, 15).unwrap());
        assert_eq!(days[0].checks[0], Some(1));
        assert_eq!(days[0].checks[1], Some(0));
        assert_eq!(days[0].checks[2], None);
        assert_eq!(days[0].checks[5], Some(1));
    }

    #[test]
    fn multiple_projects_and_sites() {
        let rows = vec![
            make_row("p1", "s1", "2025-01-15T10:00:00Z", true),
            make_row("p2", "s2", "2025-01-15T11:00:00Z", false),
        ];
        let result = build_hourly_summary(rows);
        assert!(result.contains_key("p1"));
        assert!(result.contains_key("p2"));
        assert_eq!(result["p1"]["s1"][0].checks[10], Some(1));
        assert_eq!(result["p2"]["s2"][0].checks[11], Some(0));
    }

    #[test]
    fn hours_spanning_two_days() {
        let rows = vec![
            make_row("p1", "s1", "2025-01-15T23:00:00Z", true),
            make_row("p1", "s1", "2025-01-16T00:00:00Z", false),
        ];
        let result = build_hourly_summary(rows);
        let days = &result["p1"]["s1"];
        assert_eq!(days.len(), 2);
        assert_eq!(days[0].day, NaiveDate::from_ymd_opt(2025, 1, 15).unwrap());
        assert_eq!(days[0].checks[23], Some(1));
        assert_eq!(days[1].day, NaiveDate::from_ymd_opt(2025, 1, 16).unwrap());
        assert_eq!(days[1].checks[0], Some(0));
    }
}
