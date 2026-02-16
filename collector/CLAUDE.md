# Upmon Collector

Rust service that continuously monitors site uptime. Reads `config.json` for monitor definitions (gitignored; see `config.sample.json` for format), checks health endpoints on intervals, stores results in TimescaleDB.

## Build & Run

```
cargo build
cargo run          # requires DATABASE_URL in .env
cargo check        # type-check without building
```

## Architecture

- `config.json` is the source of truth for monitors (no monitors table in DB). Gitignored — `config.sample.json` shows the schema.
- One `tokio::spawn` per monitor with independent interval loops
- Shared `reqwest::Client` and `sqlx::PgPool` across all monitors
- `sqlx::migrate!()` runs embedded migrations on startup
- Each check inserts into `monitor_checks` hypertable and upserts `monitor_status` for current state

## Database

TimescaleDB (PostgreSQL extension). Connection string via `DATABASE_URL`. Layered env: `.env` (git-tracked defaults) then `.env.local` (gitignored overrides). Two tables: `monitor_checks` hypertable for time-series history, `monitor_status` for current state per monitor — see `migrations/` for schema.

## Crate Conventions

- Runtime queries (`sqlx::query`), not compile-time macros (`sqlx::query!`)
- `rustls-tls` via reqwest (no OpenSSL dependency)
- `tracing` for structured logging, not `println!` or `log`
