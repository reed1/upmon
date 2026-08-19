# Upmon Agent

Read-only SQLite query agent deployed to remote hosts. The backend sends named view requests with filter parameters; the agent builds and executes SQL internally. Deployed via Ansible as a Jinja2 template — API keys are baked in at deploy time.

## Usage

All commands are sent via HTTP as a base64-encoded JSON payload in the `q` query parameter.

```
upmon-agent '{"q": "<base64-encoded JSON>"}'
```

### Commands

**`query`** — dispatches to a named view, builds SQL internally, executes against the site's read-only SQLite database.

Payload: `{"command": "query", "api_key": "...", "view": "logs|stats|error_count", ...}`

Views:
- **`logs`** — returns access log rows. Params: `start_time`, `end`, `exception_type`, `os`, `client_type`, `method`, `order_by`, `order_dir`, `limit` (default 100, capped at 1000), `start_id`. `start_id` is a keyset cursor: rows are returned strictly after the row with that id in the requested ordering (ties broken by `id`).
- **`stats`** — returns summary, distributions, and volume data. Params: `start_time`, `end`, `exception_type`, `os`, `client_type`, `method`.
- **`error_count`** — returns count of unexpected exceptions in a time range. Params: `start_time`, `end`.
- **`frontend_errors`** — returns browser error rows. Params: `start_time`, `end`, `kind`, `fingerprint`, `session_id`, `os`, `client_type`, `order_by` (`epoch_sec`, `kind`, `error_class`, `page_url`), `order_dir`, `limit`, `start_id` — same keyset semantics as `logs`.
- **`frontend_error_stats`** — returns summary, distributions, volume, and `top_errors` (20 most frequent fingerprints, each carrying its most recent occurrence).
- **`frontend_error_count`** — returns count of browser errors in a time range, for the nightly rollup.

Sites adopt the `frontend_error` table on their own schedule. When it is absent the three frontend views return empty results rather than failing, so one un-migrated host cannot break a fleet-wide deploy.

**`cleanup`** — deletes rows older than `retention_days` from both tables for the authenticated site. Returns `{"deleted": <count>, "frontend_deleted": <count|null>}` (`null` when the site has no `frontend_error` table).

Payload: `{"command": "cleanup", "api_key": "...", "retention_days": <int>}`

## Output Contract

All output goes to stdout as JSON: `{"error": <string|null>, "result": <object|null>}`. Never writes to stderr. Always exits 0. Host applications should parse and pass through the JSON as-is.

## Config

`config.json` (gitignored; see `config.sample.json`). Each site has `api_key`, `db_path`, and `retention_days`.

## Integrating Access Logging in a New Project

See the top-level `docs/` directory for guides on adding Upmon-compatible access logging to an application:

- [access-log-writing.md](../../../docs/access-log-writing.md) — SQLite schema, middleware, sanitization, skip rules
- [access-log-exception-testing.md](../../../docs/access-log-exception-testing.md) — exception classification and verification
- [access-log-endpoint.md](../../../docs/access-log-endpoint.md) — `/health/agent` endpoint for remote querying
- [frontend-error-writing.md](../../../docs/frontend-error-writing.md) — `frontend_error` table, the browser client, and the `/health/frontend-error` endpoint

## Access Log SQLite Schema

The agent reads from a SQLite database created by the monitored application's access logger:

```sql
CREATE TABLE access_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  epoch_sec INTEGER NOT NULL,     -- Unix epoch seconds
  client_ip TEXT NOT NULL,
  method TEXT NOT NULL,           -- HTTP method
  path TEXT NOT NULL,
  query TEXT,                     -- JSON string
  body TEXT,                      -- JSON string
  user_id INTEGER,
  status_code INTEGER,
  duration_ms REAL NOT NULL,
  user_agent TEXT,
  os TEXT,
  client_type TEXT NOT NULL,
  app_version TEXT,
  files TEXT,                     -- JSON string
  exception_class TEXT,
  exception_message TEXT,
  exception_is_unexpected INTEGER,  -- NULL = no exception, 0 = expected, 1 = unexpected
  exception_traceback TEXT          -- JSON string
);

CREATE INDEX idx_access_log_epoch_sec ON access_log (epoch_sec);
CREATE INDEX idx_access_log_unexpected_exceptions
  ON access_log (epoch_sec) WHERE exception_is_unexpected = 1;
```

## Frontend Error SQLite Schema

Lives in the same database, written by the app's `/health/frontend-error` endpoint:

```sql
CREATE TABLE frontend_error (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  epoch_sec INTEGER NOT NULL,
  client_ip TEXT NOT NULL,
  kind TEXT NOT NULL,             -- 'error' | 'unhandledrejection' | 'manual'
  error_class TEXT,
  message TEXT NOT NULL,
  stack TEXT,
  page_url TEXT NOT NULL,
  source_url TEXT,
  line_no INTEGER,
  col_no INTEGER,
  fingerprint TEXT NOT NULL,      -- groups occurrences of the same bug
  session_id TEXT,
  user_id INTEGER,
  user_agent TEXT,
  os TEXT,
  client_type TEXT NOT NULL,
  app_version TEXT
);

CREATE INDEX idx_frontend_error_epoch_sec ON frontend_error (epoch_sec);
CREATE INDEX idx_frontend_error_fingerprint ON frontend_error (fingerprint, epoch_sec);
```
