# Upmon Backend

Python/FastAPI HTTP API serving monitor status data from TimescaleDB and the Vue frontend. Gates API routes with a shared `x-api-key` header and authorizes per-user via the Pangolin-injected `remote-email` header.

## Access control

The deployment sits behind Pangolin (which handles authentication). Per-user **authorization** is driven by the `remote-email` header Pangolin injects. Config lives in git-tracked `users.yaml`, loaded by `access.py` and hot-reloaded on change.

- `role: admin` — sees every project. `role: viewer` — restricted to a required, non-empty `project_ids` list (`project_ids` are collector project IDs, e.g. `elogbook-tht`).
- `get_current_user` dependency resolves the caller: missing `remote-email` → 401, unknown email → 403. Routes call `user.ensure_access(project_id)` / `user.can_access(...)` to filter, and `user.ensure_admin()` for global mutations (`/cleanup/run`).
- If `users.yaml` is absent, access control is **disabled** (every request treated as admin) — preserving pre-access-control behavior. `x-api-key` is a shared app gate baked into the SPA, not a per-user identity.

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
