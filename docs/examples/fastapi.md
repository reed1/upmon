# Access Log — FastAPI

FastAPI middleware implementation for upmon access logging. See [access-log-writing.md](../access-log-writing.md) for schema and rules.

## Middleware

```python
import json
import sqlite3
import time
import traceback

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException


SKIP_PATHS = {"/health", "/health/agent"}
SENSITIVE_BODY_FIELDS = {"password", "password_confirmation", "password_new", "current_password"}


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

            if user_id is not None or status_code != 404:
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


def sanitize_body(body: dict | None) -> dict | None:
    if not body:
        return body
    return {k: "[REDACTED]" if k in SENSITIVE_BODY_FIELDS else v for k, v in body.items()}


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

## SQLite Setup

```python
import sqlite3
from pathlib import Path


def init_access_log_db(db_path: str = "run/access_log.db") -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            epoch_sec INTEGER NOT NULL,
            client_ip TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            query TEXT,
            body TEXT,
            user_id INTEGER,
            status_code INTEGER,
            duration_ms REAL NOT NULL,
            user_agent TEXT,
            os TEXT,
            client_type TEXT NOT NULL,
            app_version TEXT,
            files TEXT,
            exception_class TEXT,
            exception_message TEXT,
            exception_is_unexpected INTEGER,
            exception_traceback TEXT
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_access_log_epoch_sec ON access_log (epoch_sec)")
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_access_log_unexpected_exceptions
        ON access_log (epoch_sec) WHERE exception_is_unexpected = 1
    """)
    return db
```

## Registering the Middleware

```python
db = init_access_log_db()
app.add_middleware(AccessLogMiddleware, db=db)
```
