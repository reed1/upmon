use axum::extract::{Query, State};
use axum::http::{HeaderMap, StatusCode};
use axum::response::Redirect;
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;
use sqlx::PgPool;
use tokio::net::TcpListener;
use tower_http::services::{ServeDir, ServeFile};
use tracing::info;

use crate::db;
use crate::models::{HourlySummary, MonitorStatus};

#[derive(Clone)]
struct AppState {
    pool: PgPool,
    api_key: String,
}

pub async fn serve(pool: PgPool, api_key: String, port: u16, frontend_dir: String) {
    let state = AppState { pool, api_key };

    let frontend_service = ServeDir::new(&frontend_dir)
        .fallback(ServeFile::new(format!("{frontend_dir}/index.html")));

    let app = Router::new()
        .route("/", get(|| async { Redirect::permanent("/frontend") }))
        .route("/api/v1/status", get(status_handler))
        .route("/api/v1/daily-summary", get(daily_summary_handler))
        .nest_service("/frontend", frontend_service)
        .with_state(state);

    let listener = TcpListener::bind(("0.0.0.0", port))
        .await
        .expect("failed to bind HTTP listener");
    info!(port, "HTTP server listening");
    axum::serve(listener, app)
        .await
        .expect("HTTP server error");
}

#[derive(Deserialize)]
struct StatusQuery {
    project_id: Option<String>,
}

async fn status_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<StatusQuery>,
) -> Result<Json<Vec<MonitorStatus>>, StatusCode> {
    let key = headers
        .get("x-api-key")
        .and_then(|v| v.to_str().ok())
        .ok_or(StatusCode::UNAUTHORIZED)?;

    if key != state.api_key {
        return Err(StatusCode::UNAUTHORIZED);
    }

    let statuses = db::get_monitor_statuses(&state.pool, query.project_id.as_deref())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(statuses))
}

#[derive(Deserialize)]
struct DailySummaryQuery {
    project_id: Option<String>,
    days: Option<i32>,
}

async fn daily_summary_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<DailySummaryQuery>,
) -> Result<Json<HourlySummary>, StatusCode> {
    let key = headers
        .get("x-api-key")
        .and_then(|v| v.to_str().ok())
        .ok_or(StatusCode::UNAUTHORIZED)?;

    if key != state.api_key {
        return Err(StatusCode::UNAUTHORIZED);
    }

    let days = query.days.unwrap_or(7).clamp(1, 90);

    let summary = db::get_hourly_summary(&state.pool, query.project_id.as_deref(), days)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(summary))
}
