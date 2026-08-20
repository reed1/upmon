# Step 2 — Access Log

Record every request in a local SQLite database. The upmon agent reads that database later; the
application only ever writes to it.

```
App receives request --> Middleware logs to SQLite --> (step 3) upmon-agent reads from SQLite
```

The examples in this document are Laravel. For other frameworks see
[Other Frameworks](#other-frameworks) at the bottom — the schema and the rules are identical, only
the wiring differs.

## 1. Schema

Create the database on startup with WAL mode enabled, creating the directory if it does not exist.

Recommended path: `run/access_log.db` relative to the service's working directory. For Laravel, use
`storage/logs/access_log/access_log.db`.

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
    exception_traceback TEXT             -- JSON string; only populated when exception_is_unexpected = 1
);

CREATE INDEX IF NOT EXISTS idx_access_log_epoch_sec
    ON access_log (epoch_sec);
CREATE INDEX IF NOT EXISTS idx_access_log_unexpected_exceptions
    ON access_log (epoch_sec) WHERE exception_is_unexpected = 1;
```

## 2. SQLite storage

A singleton that owns the connection and inserts rows.

`app/Services/AccessLog.php`:

```php
<?php

namespace App\Services;

use PDO;

class AccessLog
{
    private PDO $pdo;

    public function __construct()
    {
        $path = config('yourapp.access_log_path');

        $dir = dirname($path);
        if (!is_dir($dir)) {
            mkdir($dir, 0755, true);
        }

        $this->pdo = new PDO("sqlite:$path");
        $this->pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $this->pdo->exec('PRAGMA journal_mode=WAL');

        $this->pdo->exec("
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
        ");
        $this->pdo->exec("
            CREATE INDEX IF NOT EXISTS idx_access_log_epoch_sec
                ON access_log (epoch_sec)
        ");
        $this->pdo->exec("
            CREATE INDEX IF NOT EXISTS idx_access_log_unexpected_exceptions
                ON access_log (epoch_sec) WHERE exception_is_unexpected = 1
        ");
    }

    public function insert(array $row): void
    {
        $columns = implode(', ', array_keys($row));
        $placeholders = implode(', ', array_fill(0, count($row), '?'));

        $stmt = $this->pdo->prepare("INSERT INTO access_log ($columns) VALUES ($placeholders)");
        $stmt->execute(array_values($row));
    }
}
```

Config (`config/yourapp.php`):

```php
'access_log_enabled' => env('ACCESS_LOG_ENABLED', true),
'access_log_path' => storage_path('logs/access_log/access_log.db'),
```

Service provider:

```php
$this->app->singleton(\App\Services\AccessLog::class);
```

## 3. Middleware

Wrap every request and insert one row on completion, success or failure. Laravel's `terminate()`
runs after the response has been sent, so logging adds no latency to the request.

`app/Http/Middleware/AccessLog.php`:

```php
<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Exception\HttpException;
use Illuminate\Validation\ValidationException;
use App\Services\AccessLog as AccessLogService;

class AccessLog
{
    private const SENSITIVE_FIELDS = [
        'password',
        'password_confirmation',
        'current_password',
        'new_password',
        'new_password_confirmation',
    ];

    public function handle(Request $request, Closure $next): Response
    {
        if (
            !config('yourapp.access_log_enabled')
            || $request->isMethod('OPTIONS')
            || str_starts_with($request->getPathInfo(), '/health')
        ) {
            return $next($request);
        }

        $data = ['start' => hrtime(true)];

        $response = $next($request);
        $data['status'] = $response->getStatusCode();

        $e = $response->exception ?? null;
        if ($e) {
            $data['exc_class'] = get_class($e);
            $data['exc_message'] = $e->getMessage();

            // Classify your app's expected exception types here
            if ($e instanceof HttpException || $e instanceof ValidationException) {
                $data['exc_unexpected'] = 0;
            } else {
                $data['exc_unexpected'] = 1;
                $data['exc_traceback'] = json_encode(explode("\n", $e->getTraceAsString()));
            }
        }

        $request->attributes->set('_access_log', $data);

        return $response;
    }

    public function terminate(Request $request, Response $response): void
    {
        $data = $request->attributes->get('_access_log');
        if ($data === null) {
            return;
        }

        $statusCode = $data['status'] ?? $response->getStatusCode();
        $userId = Auth::id();

        if ($statusCode === 404 && $userId === null) {
            return;
        }

        $durationMs = round((hrtime(true) - $data['start']) / 1_000_000, 2);
        $forwarded = $request->header('X-Forwarded-For');
        $clientIp = $forwarded ? explode(',', $forwarded)[0] : $request->ip();
        $queryParams = $request->query();
        $body = !$request->isMethod('GET') ? self::redactSensitive($request->all()) : null;

        $files = null;
        if ($request->allFiles()) {
            $fileList = [];
            foreach ($request->allFiles() as $fieldname => $uploadedFiles) {
                $uploadedFiles = is_array($uploadedFiles) ? $uploadedFiles : [$uploadedFiles];
                foreach ($uploadedFiles as $file) {
                    $fileList[] = [
                        'fieldname' => $fieldname,
                        'originalname' => $file->getClientOriginalName(),
                        'mimetype' => $file->getClientMimeType(),
                        'size' => $file->getSize(),
                    ];
                }
            }
            if ($fileList) {
                $files = json_encode($fileList);
            }
        }

        app(AccessLogService::class)->insert([
            'epoch_sec' => time(),
            'client_ip' => $clientIp,
            'method' => $request->method(),
            'path' => $request->getPathInfo(),
            'query' => $queryParams ? json_encode($queryParams) : null,
            'body' => $body ? json_encode($body) : null,
            'user_id' => $userId,
            'status_code' => $statusCode,
            'duration_ms' => $durationMs,
            'user_agent' => $request->userAgent(),
            'os' => self::parseOs($request->userAgent()),
            'client_type' => $request->header('X-Client-Type', 'browser'),
            'app_version' => $request->header('X-App-Version'),
            'files' => $files,
            'exception_class' => $data['exc_class'] ?? null,
            'exception_message' => $data['exc_message'] ?? null,
            'exception_is_unexpected' => $data['exc_unexpected'] ?? null,
            'exception_traceback' => $data['exc_traceback'] ?? null,
        ]);
    }

    private static function redactSensitive(?array $body): ?array
    {
        if (!$body) return null;
        foreach (self::SENSITIVE_FIELDS as $field) {
            if (array_key_exists($field, $body)) {
                $body[$field] = '[REDACTED]';
            }
        }
        return $body;
    }

    private static function parseOs(?string $ua): ?string
    {
        if (!$ua) return null;
        if (str_contains($ua, 'Android')) return 'android';
        if (str_contains($ua, 'iPhone') || str_contains($ua, 'iPad')) return 'ios';
        if (str_contains($ua, 'Macintosh')) return 'macos';
        if (str_contains($ua, 'Windows')) return 'windows';
        if (str_contains($ua, 'CrOS')) return 'chromeos';
        if (str_contains($ua, 'Linux')) return 'linux';
        return null;
    }
}
```

### Skip rules

Do **not** log when any of these are true:

- `OPTIONS` requests (CORS preflight)
- Path starts with `/health` — that is the route added in step 1, and everything later steps hang
  off it. Implementations that match exact paths rather than the prefix must list each
  `/health/*` path explicitly.
- Status code is `404` **and** `user_id` is null — anonymous scanner and spam traffic

### Body sanitization

Redact sensitive fields before logging. Check the app's login, reset-password and change-password
routes for the exact field names; the common ones are in `SENSITIVE_FIELDS` above.

### Exception classification

`exception_is_unexpected` separates bugs from ordinary user errors:

| Scenario | `exception_is_unexpected` | `exception_traceback` |
|---|---|---|
| Successful request (2xx) | `NULL` | `NULL` |
| App-level exception (known user error) | `0` | `NULL` |
| Validation error | `0` | `NULL` |
| Unhandled exception (500) | `1` | Full traceback |

Expected exceptions are the ones the app raises deliberately — invalid input, not found, permission
denied. They need no traceback. Unexpected exceptions are bugs, and only they carry one, which is
what keeps the log focused on actionable failures.

### Client detection

Native apps send `X-Client-Type: app` and `X-OS: android|ios`. Everything else is a browser, so
`client_type` defaults to `"browser"` and `os` is parsed from the `User-Agent`, matching in this
order: `Android`, `iPhone`/`iPad` → ios, `Macintosh` → macos, `Windows`, `CrOS` → chromeos, `Linux`.

If the app has a native mobile client, send the headers from the frontend (Capacitor example):

```ts
headers: {
  'X-Client-Type': Capacitor.isNativePlatform() ? 'app' : 'browser',
  ...(Capacitor.isNativePlatform() && { 'X-OS': Capacitor.getPlatform() }),
}
```

Skip this if the application has no native mobile app.

## 4. Register the middleware

`bootstrap/app.php` (Laravel 11+):

```php
->withMiddleware(function (Middleware $middleware) {
    $middleware->append(\App\Http\Middleware\AccessLog::class);
})
```

On older Laravel, add it to `$middleware` in `app/Http/Kernel.php`.

## 5. Test it

Everything below runs against the local development URL — no deploy needed.

### 5.1 Enable the log and start the app

```
ACCESS_LOG_ENABLED=true
```

### 5.2 Log in, then browse

**Log in first.** A request that is both anonymous and a `404` is dropped by the skip rule, so
testing while logged out is the easiest way to see an empty table and conclude, wrongly, that
nothing works.

With a session, click through a few pages — one `GET`, one form `POST`.

### 5.3 Verify the requests landed

```bash
sqlite3 -header -column storage/logs/access_log/access_log.db \
  "SELECT path, method, status_code, user_id, duration_ms
   FROM access_log ORDER BY id DESC LIMIT 5"
```

Expect one row per request, with `user_id` set to the logged-in user, a plausible `duration_ms`,
and no `/health` rows. Check that the `POST` row's `body` has its password fields redacted.

### 5.4 Add a route that throws

Temporarily, in `routes/web.php`:

```php
Route::get('/test-exc/unexpected', fn () => throw new RuntimeException('Something went wrong unexpectedly'));
Route::get('/test-exc/expected', fn () => abort(400, 'This is a test error'));
```

Hit both in the browser while still logged in.

### 5.5 Verify the exceptions and the stacktrace

```bash
sqlite3 -header -column storage/logs/access_log/access_log.db \
  "SELECT path, status_code, exception_class, exception_message,
          exception_is_unexpected, exception_traceback IS NOT NULL AS has_traceback
   FROM access_log WHERE path LIKE '/test-exc%' ORDER BY id DESC"
```

Expected:

```
path                   status_code  exception_class  exception_message                  exception_is_unexpected  has_traceback
---------------------  -----------  ---------------  ---------------------------------  -----------------------  -------------
/test-exc/expected     400          HttpException    This is a test error               0                        0
/test-exc/unexpected   500          RuntimeException Something went wrong unexpectedly  1                        1
```

The unexpected one must have `exception_is_unexpected = 1` **and** a traceback; the expected one
must have `0` and none. Read the traceback itself to confirm it is the real stack:

```bash
sqlite3 storage/logs/access_log/access_log.db \
  "SELECT exception_traceback FROM access_log
   WHERE path = '/test-exc/unexpected' ORDER BY id DESC LIMIT 1"
```

If the classification is inverted, the `instanceof` list in the middleware does not match the
app's exception hierarchy — fix it there.

### 5.6 Remove the test routes

## 6. Commit

```
git commit -m "access log middleware and sqlite storage"
```

## Other Frameworks

- [FastAPI (Python)](step-2-examples/fastapi.md)
- [NestJS (Node/TypeScript)](step-2-examples/nestjs.md)
- [Laravel with Livewire (PHP)](step-2-examples/laravel-with-livewire.md)

---

Previous: [step 1 — health route](step-1-health-route.md). Next: step 3 (the `/health/agent`
endpoint the upmon agent queries).
