# Upmon Backend

Python/FastAPI HTTP API serving monitor status data from TimescaleDB and the Vue frontend.

## Access control

The same route handlers are mounted twice (see `main.py`), differing only in how the caller is authenticated:

- **`/api/v1/*`** — behind Pangolin SSO. `require_pangolin_user` resolves the caller from the `remote-email` header Pangolin injects. This is the path the SPA uses (no auth header — Pangolin gates it).
- **`/api-public/v1/*`** — bypasses Pangolin (see the resource's `bypass_sso_paths`). `require_service_key` authenticates the private `API_KEY` (`x-api-key` header) and grants admin. This is for background services/scripts that don't have a browser session.

Both mounts set `request.state.user`; routes read it via `get_current_user`.

**Per-user authorization** (only meaningful on `/api`, where identity is a real person) is driven by git-tracked `users.yaml`, loaded by `access.py` and hot-reloaded on change:

- `role: admin` — sees every project. `role: viewer` — restricted to a required, non-empty `project_ids` list (`project_ids` are collector project IDs, e.g. `elogbook-tht`).
- Missing `remote-email` → 401, unknown email → 403. Routes call `user.ensure_access(project_id)` / `user.can_access(...)` to filter, and `user.ensure_admin()` for global mutations (`/cleanup/run`).
- If `users.yaml` is absent, `/api` authorization is **disabled** (every request treated as admin).

The `API_KEY` is the private service key for `/api-public` only — it is **not** baked into the SPA, so a logged-in viewer cannot extract it to escalate past their `/api` restrictions.

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
