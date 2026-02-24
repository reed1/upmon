# Upmon Agent

Read-only SQLite query proxy deployed to remote hosts. The backend invokes it over SSH to fetch access log data. Deployed via Ansible as a Jinja2 template — API keys are baked in at deploy time.

## Usage

```
upmon-agent query '{"api_key": "...", "sql": "SELECT ...", "bindings": [...]}'
upmon-agent cleanup
```

- `query` — executes read-only SQL against the site's SQLite database, returns `{"result": {"columns": [...], "rows": [...]}}`.
- `cleanup` — deletes rows older than `retention_days` from all configured sites.

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
  platform TEXT,
  client_type TEXT,
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
