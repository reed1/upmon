# Access Log Writing

How to add request logging to a backend application. Each request is recorded in a local SQLite database for querying by the upmon agent.

## Architecture

```
App receives request --> Middleware logs to SQLite --> upmon-agent reads from SQLite
```

## SQLite Database

Create on startup with WAL mode enabled. Create the directory if it doesn't exist.

Recommended path: `run/access_log.db` relative to the service's working directory. For Laravel, use `storage/logs/access_log/access_log.db`.

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

## Request Logging Middleware

Wrap every request. On completion (success or error), insert a row into `access_log`.

### Body sanitization

Before logging, redact sensitive fields from the request body. Check your app's login, reset-password, and change-password routes to identify the exact field names. Common ones: `password`, `password_confirmation`, `password_new`, `current_password`.

### Skip rules

Do **not** log when any of these are true:

- `OPTIONS` requests (CORS preflight)
- Path starts with `/health` (infrastructure noise from upmon polling)
- Status code is `404` **and** `user_id` is null (spam/scanner traffic)

### Client detection

Native apps send `X-Client-Type: app` and `X-OS: android|ios`. Browsers are detected from `User-Agent`; `client_type` defaults to `"browser"`.

### OS parsing from User-Agent

Match in this order: `Android`, `iPhone`/`iPad` → ios, `Macintosh` → macos, `Windows`, `CrOS` → chromeos, `Linux`.

## Frontend Headers

On the frontend, send `X-Client-Type` and `X-OS` headers for native app detection (Capacitor example):

```ts
headers: {
  'X-Client-Type': Capacitor.isNativePlatform() ? 'app' : 'browser',
  ...(Capacitor.isNativePlatform() && { 'X-OS': Capacitor.getPlatform() }),
}
```

## Framework Examples

See [examples/](examples/) for complete implementations:

- [FastAPI (Python)](examples/fastapi.md)
- [NestJS (Node/TypeScript)](examples/nestjs.md)
- [Laravel (PHP)](examples/laravel.md)
- [Laravel with Livewire (PHP)](examples/laravel-with-livewire.md)
