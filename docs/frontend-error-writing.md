# Frontend Error Writing

How to add browser error reporting to an application. Uncaught JavaScript errors are posted to `/health/frontend-error` and recorded in the same local SQLite database the [access log](access-log-writing.md) uses, so the upmon agent reads both through one connection.

## Architecture

```
Browser throws --> upmon-frontend-error.js --POST /health/frontend-error--> SQLite --> upmon-agent
```

An uptime check and an access log can both look clean while the page is broken for the user — the request returned 200 and the failure happened after it. This closes that gap.

## Schema

Added to the **existing** `access_log.db` — no second database, no agent config change.

```sql
CREATE TABLE IF NOT EXISTS frontend_error (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epoch_sec INTEGER NOT NULL,
    client_ip TEXT NOT NULL,
    kind TEXT NOT NULL,              -- "error", "unhandledrejection", "manual"
    error_class TEXT,                -- "TypeError"
    message TEXT NOT NULL,
    stack TEXT,
    page_url TEXT NOT NULL,          -- URL the user was on
    source_url TEXT,                 -- script that threw
    line_no INTEGER,
    col_no INTEGER,
    fingerprint TEXT NOT NULL,       -- groups occurrences of the same bug
    session_id TEXT,                 -- correlates errors within one browsing session
    user_id INTEGER,
    user_agent TEXT,
    os TEXT,                         -- "android", "ios", "windows", "macos", "linux"
    client_type TEXT NOT NULL,       -- "app" or "browser"
    app_version TEXT
);

CREATE INDEX IF NOT EXISTS idx_frontend_error_epoch_sec
    ON frontend_error (epoch_sec);
CREATE INDEX IF NOT EXISTS idx_frontend_error_fingerprint
    ON frontend_error (fingerprint, epoch_sec);
```

Column names mirror `access_log` on purpose (`epoch_sec`, `client_ip`, `os`, `client_type`, `app_version`) so agent and dashboard code is shared.

Retention is handled by the existing nightly `cleanup` command — the agent prunes `frontend_error` on the same `retention_days` as `access_log`. Nothing extra to schedule.

## Browser Client

Copy [examples/upmon-frontend-error.js](examples/upmon-frontend-error.js) into the app's static assets and load it **before** application code:

```html
<script>window.UPMON_FRONTEND_ERROR = { appVersion: '1.4.2' };</script>
<script src="/static/upmon-frontend-error.js"></script>
```

Options: `endpoint` (default `/health/frontend-error`), `appVersion`, `maxEvents` (default 10).

It hooks `window.onerror` and `unhandledrejection`. Failed `<img>`/`<script>`/`<link>` loads are deliberately ignored — they are not application errors and the server already sees the failed requests.

### Framework hooks

Errors caught by a framework's own boundary never reach `window.onerror`. Forward them:

```js
// Vue 3
app.config.errorHandler = (err, instance, info) => window.upmon.captureError(err, info);

// React error boundary
componentDidCatch(error, info) { window.upmon.captureError(error, info.componentStack); }

// Manual
try { risky(); } catch (e) { window.upmon.captureError(e, 'checkout'); throw e; }
```

### Spam control

The client is the first line of defence, because a render loop can throw thousands of times per second:

- **Dedupe by fingerprint** — each distinct error is reported once per page load. The fingerprint masks digits and UUIDs in the message, so `user 12 not found` and `user 99 not found` group together.
- **Hard cap** of `maxEvents` (default 10) reports per page load.
- Truncation before send: message 2000 chars, stack 8000, URLs 500.

Dedupe is per page load, not per session: a bug that breaks every page should register on every page. The cap bounds it either way.

The client never throws. Every entry point swallows unconditionally — a reporter that throws inside an error handler causes the exact cascade it exists to detect.

## Endpoint

`POST /health/frontend-error`, JSON body, returns `204 No Content`. Never echo the input back.

Payload from the client:

```json
{ "kind": "error", "message": "x is not a function", "error_class": "TypeError",
  "stack": "...", "page_url": "https://app/dashboard", "source_url": "https://app/app.js",
  "line_no": 10, "col_no": 5, "session_id": "…", "fingerprint": "a1b2c3d4", "app_version": "1.4.2" }
```

The server derives `epoch_sec`, `client_ip`, `user_agent`, `os`, `client_type` from the request, reusing the access log's existing `get_client_info` / user-agent parsing. **`user_id` comes from the app's own session, never from the payload.**

### This endpoint is unauthenticated

Unlike `/health/agent`, which is protected by the agent API key in its payload, this one must accept writes from any browser that can load the page — a browser cannot hold a secret. The realistic risk is disk-fill and log spam, not data theft. Every implementation must apply these guards:

| Guard | Response |
| --- | --- |
| Body larger than 16 KB | `413` |
| More than 30 reports/min from one IP | `429` |
| `Origin` header present and not an allowed origin | `403` |
| `kind` not one of `error`, `unhandledrejection`, `manual` | `400` |

Truncate every text field again at insert — the client is untrusted. Silent failure is correct: the client discards non-2xx responses, so a rejected report never disturbs the user.

### Skip rule

Add `/health/frontend-error` to the access log middleware's skip list. Otherwise every browser error also writes an `access_log` row. Note that some implementations match `/health` exactly rather than by prefix — check yours.

## Rollout

The upmon agent tolerates sites that have not adopted this yet: the frontend error views return empty results and cleanup still prunes `access_log`. Add the table and endpoint app by app, in any order.

## Framework Examples

- [FastAPI (Python)](examples/fastapi.md)
- [NestJS (Node/TypeScript)](examples/nestjs.md)
- [Laravel (PHP)](examples/laravel.md)
- [Laravel with Livewire (PHP)](examples/laravel-with-livewire.md)
