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
- `GET /health/agent` — accepts a single `q` query param containing a base64-encoded JSON payload. Shells out to the `upmon-agent` script and returns its JSON output. The agent path comes from an env var / config.

```python
import json
import os
import subprocess

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/health")


@router.get("")
def health():
    return {"status": "UP"}


@router.get("/agent")
def health_agent(q: str = Query()):
    agent_path = os.environ.get("UPMON_AGENT_PATH")
    if not agent_path:
        raise HTTPException(500, "UPMON_AGENT_PATH not configured")

    args = json.dumps({"q": q})
    result = subprocess.run(
        ["python3", agent_path, "query", args],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(result.stdout)
```

## 2. SQLite Database

Create on startup with WAL mode enabled.

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
    os TEXT,                             -- "android", "ios", "windows", "macos", "linux"
    client_type TEXT NOT NULL,           -- "app" or "browser"
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

### Body sanitization

Before logging, redact sensitive fields from the request body. Check your app's login, reset-password, and change-password routes to identify the exact field names. Common ones:

```python
SENSITIVE_BODY_FIELDS = {"password", "password_confirmation", "password_new", "current_password"}


def sanitize_body(body: dict | None) -> dict | None:
    if not body:
        return body
    return {k: "[REDACTED]" if k in SENSITIVE_BODY_FIELDS else v for k, v in body.items()}
```

### Skip rules

Do **not** log when any of these are true:

- `OPTIONS` requests (CORS preflight)
- Path is `/health` or `/health/agent` (infrastructure noise from upmon polling)
- Status code is `404` **and** `user_id` is null (spam/scanner traffic)

### Example (FastAPI)

```python
import json
import sqlite3
import time
import traceback

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException


SKIP_PATHS = {"/health", "/health/agent"}


class AccessLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, db: sqlite3.Connection):
        super().__init__(app)
        self.db = db

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS" or request.url.path in SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500
        exc_class = None
        exc_message = None
        exc_is_unexpected = None
        exc_traceback = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except HTTPException as e:
            status_code = e.status_code
            exc_class = type(e).__name__
            exc_message = e.detail
            exc_is_unexpected = 0
            raise
        except Exception as e:
            status_code = 500
            exc_class = type(e).__name__
            exc_message = str(e)
            exc_is_unexpected = 1
            exc_traceback = json.dumps(traceback.format_exception(e))
            raise
        finally:
            user_id = getattr(request.state, "user_id", None)

            if status_code == 404 and user_id is None:
                return

            os, client_type = get_client_info(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            forwarded = request.headers.get("x-forwarded-for")
            client_ip = forwarded.split(",")[0].strip() if forwarded else request.client.host
            query_params = dict(request.query_params)

            # request.state.log_body is set manually in the app's core module (dict or None)
            body = sanitize_body(getattr(request.state, "log_body", None))
            body_insert = json.dumps(body) if body else None

            self.db.execute(
                """INSERT INTO access_log (
                    epoch_sec, client_ip, method, path, query, body, user_id,
                    status_code, duration_ms, user_agent, os, client_type,
                    app_version, exception_class, exception_message,
                    exception_is_unexpected, exception_traceback
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    int(time.time()),
                    client_ip,
                    request.method,
                    request.url.path,
                    json.dumps(query_params) if query_params else None,
                    body_insert,
                    user_id,
                    status_code,
                    duration_ms,
                    request.headers.get("user-agent"),
                    os,
                    client_type,
                    request.headers.get("x-app-version"),
                    exc_class,
                    exc_message,
                    exc_is_unexpected,
                    exc_traceback,
                ),
            )
            self.db.commit()


def get_client_info(request: Request) -> tuple[str | None, str]:
    """Returns (os, client_type).

    - Native apps send X-Client-Type: app and X-OS: android|ios.
    - Browsers are detected from User-Agent; client_type defaults to "browser".
    """
    client_type = request.headers.get("x-client-type")

    if client_type == "app":
        return request.headers.get("x-os"), "app"

    return parse_os_from_user_agent(request.headers.get("user-agent")), "browser"


def parse_os_from_user_agent(ua: str | None) -> str | None:
    if not ua:
        return None
    if "Android" in ua:
        return "android"
    if "iPhone" in ua or "iPad" in ua:
        return "ios"
    if "Macintosh" in ua:
        return "macos"
    if "Windows" in ua:
        return "windows"
    if "CrOS" in ua:
        return "chromeos"
    if "Linux" in ua:
        return "linux"
    return None
```

On the frontend, send `X-Client-Type` and `X-OS` headers (Capacitor example):

```ts
headers: {
  'X-Client-Type': Capacitor.isNativePlatform() ? 'app' : 'browser',
  ...(Capacitor.isNativePlatform() && { 'X-OS': Capacitor.getPlatform() }),
}
```
