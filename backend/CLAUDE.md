# Upmon Backend

Rust backend for site uptime monitoring. Reads `config.json` for monitor definitions, checks health endpoints on intervals, stores results in PostgreSQL.

## Build & Run

```
cargo build
cargo run          # requires DATABASE_URL in .env
cargo check        # type-check without building
```

## Architecture

- `config.json` is the source of truth for monitors (no monitors table in DB)
- One `tokio::spawn` per monitor with independent interval loops
- Shared `reqwest::Client` and `sqlx::PgPool` across all monitors
- `sqlx::migrate!()` runs embedded migrations on startup

## Database

PostgreSQL. Connection string via `DATABASE_URL`. Layered env: `.env` (git-tracked defaults) then `.env.local` (gitignored overrides). Single `check_results` table — see `migrations/` for schema.

## Crate Conventions

- Runtime queries (`sqlx::query`), not compile-time macros (`sqlx::query!`)
- `rustls-tls` via reqwest (no OpenSSL dependency)
- `tracing` for structured logging, not `println!` or `log`
