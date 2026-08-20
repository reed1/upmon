# Upmon

Uptime monitoring system. Monorepo with 4 components:

- **collector/** — Rust service that runs HTTP health checks on configured intervals and stores results in TimescaleDB. Monitor definitions live in `collector/config.json` (gitignored; see `config.sample.json` for format).
- **backend/** — Python/FastAPI API server. Reads from TimescaleDB and serves `/api/v1/status` and `/api/v1/daily-summary`. Also serves the built frontend at `/frontend/`. Auth via `x-api-key` header.
- **frontend/** — Vue 3 + Vite + Tailwind CSS v4 SPA. Displays monitor status and hourly uptime grids. Built as static files served by backend.
- **ansible/** — Deployment playbooks targeting the `sgtent` host (upmon backend/collector/frontend) and remote agent hosts. Each component runs as a systemd user service.

## Architecture

- Data flow: Collector → TimescaleDB ← Backend API ← Frontend
- Agent flow: Backend API → remote `/health/agent` endpoint → `upmon-agent` script → SQLite access logs
- Frontend error flow: monitored app's browser → its own `/health/frontend-error` endpoint → same SQLite DB (`frontend_error` table) → read back through `upmon-agent`

## Documentation

**docs/site-implementation-steps/** is the ordered walkthrough for making an application
Upmon-compatible — one numbered document per step, each ending in a commit. Start at
`step-1-health-route.md`.
