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
- API endpoint: `GET /api/v1/access-logs/sites` — list configured agent sites
- API endpoint: `GET /api/v1/access-logs/sites/{project_id}/{site_key}/logs` — proxy access logs from remote agent
- API endpoint: `GET /api/v1/access-logs/sites/{project_id}/{site_key}/stats` — proxy access log stats from remote agent
- Serves frontend static files at `/frontend` from `FRONTEND_DIR` (defaults to `../frontend/dist`)
- SPA fallback: unknown paths under `/frontend` serve `index.html`
- Reads from `monitor_status` table (written by the collector service)
- No migrations — schema owned by the collector

## Agent

The backend proxies access log queries to remote agents. Config in `agents.json` (gitignored; see `agents.sample.json`). Each site has `project_id`, `site_key`, `agent_url`, and `agent_api_key`. The agent script (`scripts/upmon-agent/main.py`) is a Jinja2 template deployed via Ansible — API keys are baked in at deploy time. Multiple sites sharing a host get all their keys merged into one script.

## Database

TimescaleDB (PostgreSQL extension). Connection string via `DATABASE_URL`. Layered env: `.env` (git-tracked defaults) then `.env.local` (gitignored overrides).
