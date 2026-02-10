# Upmon Backend

Rust/Axum HTTP API serving monitor status data from TimescaleDB and the Vue frontend. Authenticates API routes via `x-api-key` header.

## Build & Run

```
cargo build
cargo run          # requires DATABASE_URL, API_KEY, LISTEN_PORT, FRONTEND_DIR in env
cargo check        # type-check without building
```

## Architecture

- Axum router with shared `AppState` (PgPool + API key)
- API endpoint: `GET /api/v1/status?project_id=<optional>`
- Serves frontend static files at `/frontend` from `FRONTEND_DIR` (defaults to `../frontend/dist`)
- SPA fallback: unknown paths under `/frontend` serve `index.html`
- Reads from `monitor_status` table (written by the collector service)
- No migrations — schema owned by the collector

## Database

TimescaleDB (PostgreSQL extension). Connection string via `DATABASE_URL`. Layered env: `.env` (git-tracked defaults) then `.env.local` (gitignored overrides).

## Crate Conventions

- Runtime queries (`sqlx::query`), not compile-time macros (`sqlx::query!`)
- `tracing` for structured logging, not `println!` or `log`
