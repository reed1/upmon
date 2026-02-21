# Upmon Backend

Python/FastAPI HTTP API serving monitor status data from TimescaleDB and the Vue frontend. Authenticates API routes via `x-api-key` header.

## Build & Run

```
uv sync              # install dependencies
uv run fastapi dev              # start dev server (requires DATABASE_URL, API_KEY in env)
uv run pytest        # run tests
```

## Architecture

- FastAPI app with asyncpg connection pool
- API endpoint: `GET /api/v1/status?project_id=<optional>` — current monitor status
- API endpoint: `GET /api/v1/daily-summary?project_id=<optional>&days=<1-90>` — daily uptime aggregation from `monitor_checks`
- Serves frontend static files at `/frontend` from `FRONTEND_DIR` (defaults to `../frontend/dist`)
- SPA fallback: unknown paths under `/frontend` serve `index.html`
- Reads from `monitor_status` table (written by the collector service)
- No migrations — schema owned by the collector

## Database

TimescaleDB (PostgreSQL extension). Connection string via `DATABASE_URL`. Layered env: `.env` (git-tracked defaults) then `.env.local` (gitignored overrides).
