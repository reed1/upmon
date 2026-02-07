# Upmon Future Roadmap

## Phase 2: REST API

- axum HTTP server running alongside the scheduler
- API key authentication middleware
- Endpoints:
  - `GET /api/status` — current up/down for all monitors
  - `GET /api/projects` — list projects and their monitors
  - `GET /api/projects/:id/history` — paginated check history for a project

## Phase 3: Retention + Alerts

- Background task that deletes `check_results` rows older than `retention_days`
- Webhook alerts (Discord/Slack) on N consecutive failures
- Configurable alert thresholds per monitor

## Phase 4: Next.js Frontend

- Dashboard consuming the REST API
- Real-time status overview with response time charts
- Per-project drill-down with history table

## Phase 5: Integration Tests

- testcontainers for PostgreSQL
- End-to-end tests: load config, run checks against mock HTTP server, verify DB rows
- CI pipeline with `cargo test`
