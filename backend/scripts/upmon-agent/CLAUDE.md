# Upmon Agent

Read-only SQLite query agent deployed to remote hosts. The backend sends named view requests with filter parameters; the agent builds and executes SQL internally. Deployed via Ansible as a Jinja2 template — API keys are baked in at deploy time.

## Usage

All commands are sent via HTTP as a base64-encoded JSON payload in the `q` query parameter.

```
upmon-agent '{"q": "<base64-encoded JSON>"}'
```

### Commands

**`query`** — dispatches to a named view, builds SQL internally, executes against the site's read-only SQLite database.

Payload: `{"command": "query", "api_key": "...", "view": "logs|stats", ...}`

Views:
- **`logs`** — returns recent access log rows. Params: `start`, `end`, `exception_type`, `os`, `client_type`, `method`, `order_by`, `order_dir`.
- **`stats`** — returns summary, distributions, and volume data. Params: `start`, `end`, `exception_type`, `os`, `client_type`, `method`.

**`cleanup`** — deletes rows older than `retention_days` for the authenticated site. Returns `{"deleted": <count>}`.

Payload: `{"command": "cleanup", "api_key": "...", "retention_days": <int>}`

## Config

`config.json` (gitignored; see `config.sample.json`). Each site has `api_key`, `db_path`, and `retention_days`.

## Integrating Access Logging in a New Project

See [ACCESS_LOG_INTEGRATION.md](ACCESS_LOG_INTEGRATION.md) for a step-by-step guide on adding Upmon-compatible access logging to a Python/FastAPI application.

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
