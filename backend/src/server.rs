use axum::extract::{Query, State};
use axum::http::{HeaderMap, StatusCode};
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;
use tokio::net::TcpListener;
use tracing::info;

use crate::models::{CacheEntry, StatusCache};

#[derive(Clone)]
struct AppState {
    cache: StatusCache,
    api_key: String,
}

pub async fn serve(cache: StatusCache, api_key: String, port: u16) {
    let state = AppState { cache, api_key };
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
) -> Result<Json<Vec<CacheEntry>>, StatusCode> {
    let key = headers
        .get("x-api-key")
        .and_then(|v| v.to_str().ok())
        .ok_or(StatusCode::UNAUTHORIZED)?;

    if key != state.api_key {
        return Err(StatusCode::UNAUTHORIZED);
    }

    let cache = state.cache.read().unwrap();
    let mut results: Vec<CacheEntry> = cache
        .values()
        .filter(|e| match &query.project_id {
            Some(id) => e.result.project_id == *id,
            None => true,
        })
        .cloned()
        .collect();
    results.sort_by(|a, b| {
        (&a.result.project_id, &a.result.site_key)
            .cmp(&(&b.result.project_id, &b.result.site_key))
    });

    Ok(Json(results))
}
