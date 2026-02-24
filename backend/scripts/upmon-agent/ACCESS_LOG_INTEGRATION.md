# Access Log Integration Guide

How to add Upmon-compatible access logging to any backend project.

## Architecture

```
Upmon Backend --SSH--> GET /health/agent --subprocess--> upmon-agent query --> SQLite
```

The monitored app writes requests to a local SQLite database. Upmon's agent (deployed alongside via Ansible) reads from it.

## 1. Health Endpoints

Mount a router at `/health` with two routes:

- `GET /health` — returns `{"status": "UP"}`. Used by uptime checks.
- `GET /health/agent` — accepts `api_key`, `sql`, `bindings` as query params. Shells out to the `upmon-agent` script (`python3 <UPMON_AGENT_PATH> query '<json>'`) and returns the JSON result. The agent path comes from an env var / config.

## 2. SQLite Database

Location: `<project>/run/access-log/access-log.db`. Create on startup with WAL mode enabled.

### Schema

```sql
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epoch_sec INTEGER NOT NULL,
    client_ip TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    query TEXT,                          -- JSON string
    body TEXT,                           -- JSON string
    user_id INTEGER,
    status_code INTEGER,
    duration_ms REAL NOT NULL,
    user_agent TEXT,
    platform TEXT,                       -- "web", "android", "ios"
    client_type TEXT,                    -- "app" or "browser"
    app_version TEXT,
    files TEXT,                          -- JSON string of [{fieldname, originalname, mimetype, size}]
    exception_class TEXT,
    exception_message TEXT,
    exception_is_unexpected INTEGER,     -- NULL = no exception, 0 = expected, 1 = unexpected
    exception_traceback TEXT             -- JSON string
);

CREATE INDEX IF NOT EXISTS idx_access_log_epoch_sec
    ON access_log (epoch_sec);
CREATE INDEX IF NOT EXISTS idx_access_log_unexpected_exceptions
    ON access_log (epoch_sec) WHERE exception_is_unexpected = 1;
```

## 3. Request Logging Middleware / Interceptor

Wrap every request. On completion (success or error), insert a row into `access_log`.

### Skip rules

Do **not** log when any of these are true:

- `OPTIONS` requests (CORS preflight)
- Path is `/health` or `/health/agent` (infrastructure noise from upmon polling)
- Status code is `404` **and** `user_id` is null (spam/scanner traffic)

### Pseudocode

```
on_request(req):
    if req.method == "OPTIONS" or req.path in ["/health", "/health/agent"]:
        return pass_through(req)

    start = now()

    try:
        response = handle(req)
        status_code = response.status
        exception = null
    catch error:
        status_code = error.status or 500
        is_unexpected = error is NOT a known HTTP exception
        exception = {
            class:     error.class_name,
            message:   error.message,
            is_unexpected: is_unexpected,
            traceback: is_unexpected ? error.stack_frames : null
        }
        re-raise error

    finally:
        user_id = get_authenticated_user_id(req)  -- null if unauthenticated

        if status_code == 404 and user_id is null:
            return

        insert into access_log {
            epoch_sec:    unix_timestamp(),
            client_ip:    req.headers["x-forwarded-for"].split(",")[0] or req.remote_ip,
            method:       req.method,
            path:         req.path,
            query:        json(req.query_params) or null,
            body:         json(req.body) or null,
            user_id:      user_id,
            status_code:  status_code,
            duration_ms:  round(now() - start, 2),
            user_agent:   req.headers["user-agent"],
            platform:     detect_platform(req),
            client_type:  req.headers["x-client-type"],
            app_version:  req.headers["x-app-version"],
            files:        json(uploaded_files_metadata) or null,
            exception_*:  from exception above
        }
```

### Platform detection

- If `x-client-type` is `"app"`: trust `x-platform` header (native app knows its platform).
- If `x-client-type` is `"browser"`: parse user-agent for Android/iPhone/iPad → `"android"`/`"ios"`, else `"web"`.
- If no `x-client-type`: null.
