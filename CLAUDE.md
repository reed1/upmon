# Upmon

Uptime monitoring system. Monorepo with 4 components:

- **collector/** — Rust service that runs HTTP health checks on configured intervals and stores results in TimescaleDB. Monitor definitions live in `collector/config.json` (gitignored; see `config.sample.json` for format).
- **backend/** — Rust/Axum API server. Reads from TimescaleDB and serves `/api/v1/status` and `/api/v1/daily-summary`. Also serves the built frontend at `/frontend/`. Auth via `x-api-key` header.
- **frontend/** — Vue 3 + Vite + Tailwind CSS v4 SPA. Displays monitor status and hourly uptime grids. Built as static files served by backend.
- **ansible/** — Deployment playbooks targeting the `sgtent` host. Each component runs as a systemd user service.

Data flow: Collector → TimescaleDB ← Backend API ← Frontend
