use std::sync::Arc;

use aide::axum::routing::get as api_get;
use aide::axum::ApiRouter;
use aide::generate::GenContext;
use aide::openapi::{self, OpenApi, Operation};
use aide::scalar::Scalar;
use aide::transform::TransformOpenApi;
use aide::OperationInput;
use axum::extract::FromRequestParts;
use axum::extract::{Query, State};
use axum::http::request::Parts;
use axum::http::StatusCode;
use axum::response::{Html, IntoResponse, Redirect};
use axum::routing::get;
use axum::{Extension, Json};
use indexmap::IndexMap;
use schemars::JsonSchema;
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

struct ApiKey;

impl FromRequestParts<AppState> for ApiKey {
    type Rejection = StatusCode;

    async fn from_request_parts(
        parts: &mut Parts,
        state: &AppState,
    ) -> Result<Self, Self::Rejection> {
        let key = parts
            .headers
            .get("x-api-key")
            .and_then(|v| v.to_str().ok())
            .ok_or(StatusCode::UNAUTHORIZED)?;

        if key != state.api_key {
            return Err(StatusCode::UNAUTHORIZED);
        }

        Ok(ApiKey)
    }
}

impl OperationInput for ApiKey {
    fn operation_input(_ctx: &mut GenContext, operation: &mut Operation) {
        operation
            .security
            .push(IndexMap::from([("ApiKey".into(), vec![])]));
    }
}

pub async fn serve(pool: PgPool, api_key: String, port: u16, frontend_dir: String) {
    let state = AppState { pool, api_key };

    let frontend_service = ServeDir::new(&frontend_dir)
        .fallback(ServeFile::new(format!("{frontend_dir}/index.html")));

    let mut api = OpenApi::default();

    let app = ApiRouter::new()
        .api_route("/api/v1/status", api_get(status_handler))
        .api_route("/api/v1/daily-summary", api_get(daily_summary_handler))
        .finish_api_with(&mut api, api_docs)
        .route("/", get(|| async { Redirect::permanent("/frontend") }))
        .route("/openapi.json", get(openapi_handler))
        .route("/docs", get(docs_handler))
        .nest_service("/frontend", frontend_service)
        .layer(Extension(Arc::new(api)))
        .with_state(state);

    let listener = TcpListener::bind(("0.0.0.0", port))
        .await
        .expect("failed to bind HTTP listener");
    info!(port, "HTTP server listening");
    axum::serve(listener, app)
        .await
        .expect("HTTP server error");
}

fn api_docs(api: TransformOpenApi) -> TransformOpenApi {
    api.title("Upmon API")
        .summary("Uptime monitoring API")
        .security_scheme(
            "ApiKey",
            openapi::SecurityScheme::ApiKey {
                location: openapi::ApiKeyLocation::Header,
                name: "x-api-key".into(),
                description: Some("API key for authentication".into()),
                extensions: Default::default(),
            },
        )
}

async fn openapi_handler(Extension(api): Extension<Arc<OpenApi>>) -> impl IntoResponse {
    Json(api.as_ref().clone())
}

async fn docs_handler() -> Html<String> {
    let html = Scalar::new("/openapi.json")
        .with_title("Upmon API")
        .html()
        .replacen(
            "</head>",
            "<style>:root { --scalar-font: system-ui, sans-serif !important; }</style></head>",
            1,
        );
    Html(html)
}

#[derive(Deserialize, JsonSchema)]
struct StatusQuery {
    project_id: Option<String>,
}

async fn status_handler(
    State(state): State<AppState>,
    _auth: ApiKey,
    Query(query): Query<StatusQuery>,
) -> Result<Json<Vec<MonitorStatus>>, StatusCode> {
    let statuses = db::get_monitor_statuses(&state.pool, query.project_id.as_deref())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(statuses))
}

#[derive(Deserialize, JsonSchema)]
struct DailySummaryQuery {
    project_id: Option<String>,
    days: Option<i32>,
}

async fn daily_summary_handler(
    State(state): State<AppState>,
    _auth: ApiKey,
    Query(query): Query<DailySummaryQuery>,
) -> Result<Json<HourlySummary>, StatusCode> {
    let days = query.days.unwrap_or(7).clamp(1, 90);

    let summary = db::get_hourly_summary(&state.pool, query.project_id.as_deref(), days)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(summary))
}
