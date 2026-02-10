use axum::extract::{Query, State};
use axum::http::{HeaderMap, StatusCode};
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;
use sqlx::PgPool;
use tokio::net::TcpListener;
use tracing::info;

use crate::db;
use crate::models::MonitorStatus;

#[derive(Clone)]
struct AppState {
    pool: PgPool,
    api_key: String,
}

pub async fn serve(pool: PgPool, api_key: String, port: u16) {
    let state = AppState { pool, api_key };
    let app = Router::new()
        .route("/status", get(status_handler))
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
