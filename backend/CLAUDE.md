# Upmon Backend

Python/FastAPI HTTP API serving monitor status data from TimescaleDB and the Vue frontend.

## Access control

`/api/v1/*` is gated by a per-user **API key** (`require_api_key` in `access.py`), presented as `Authorization: Bearer <key>`. `/api` bypasses Pangolin SSO. The key is never stored: it is `HMAC-SHA256(API_KEY_SECRET, email)` derived from an email in git-tracked `users.yaml`.

Callers obtain their key from **`GET /pangolin/api-key`** (`routes/api_key.py`), which stays behind Pangolin SSO. `require_pangolin_user` resolves the caller from the `remote-email` header Pangolin injects, and the route returns that user's derived key. The SPA fetches this once, then carries the Bearer token on every `/api` call. Background scripts use an admin user's key (see the CLI helper below).

On each `users.yaml` (re)load, `access.py` builds a `key → User` map, so requests are authorized by dict lookup — no per-request HMAC. `require_api_key` sets `request.state.user`; routes read it via `get_current_user`.

**Per-user authorization** is driven by `users.yaml`, hot-reloaded on change:

- `role: admin` — sees every project. `role: viewer` — restricted to a required, non-empty `project_ids` list (`project_ids` are collector project IDs, e.g. `elogbook-tht`).
- Missing/unknown Bearer key → 401. On the SSO issuer, missing `remote-email` → 401, unknown email → 403. Routes call `user.ensure_access(project_id)` / `user.can_access(...)` to filter, and `user.ensure_admin()` for global mutations (`/cleanup/run`).
- If `users.yaml` is absent, no keys are valid → every `/api` request is 401.

**External:** Pangolin must bypass SSO for `/api` (and `/health`) while keeping `/pangolin` and `/frontend` gated — set via the resource's `bypass_sso_paths`.

### Local dev

There is no Pangolin locally, so nothing injects `remote-email` and `/pangolin/api-key` would always 401. Set `DEV_IDENTITY_EMAIL` in `.env.local` to a `users.yaml` email; `require_pangolin_user` falls back to it when the header is absent, so the SPA's key fetch works unchanged. Never set it in production — a real `remote-email` header always wins, but an unset value is the only thing keeping the issuer closed.

### CLI helper

```
python -m upmon_backend.cli.get_api_key <email>   # prints the Bearer key for a users.yaml email
```

## Build & Run

```
uv sync              # install dependencies
uv run fastapi dev              # start dev server (requires DATABASE_URL, API_KEY_SECRET in env)
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
