# Access Log — Laravel

Laravel middleware implementation for upmon access logging. See [access-log-writing.md](../access-log-writing.md) for schema and rules.

## AccessLog Service

Manages the SQLite connection and inserts rows. Register as a singleton in a service provider.

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

### Config

Add to your app config (e.g. `config/yourapp.php`):

```php
'access_log_enabled' => env('ACCESS_LOG_ENABLED', true),
'access_log_path' => storage_path('logs/access_log/access_log.db'),
```

### Service Provider

```php
$this->app->singleton(\App\Services\AccessLog::class);
```

## Middleware

Uses `terminate()` to log after the response is sent to the client, avoiding added latency.

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
            'client_type' => 'browser',
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

## Registering the Middleware

Add to your `bootstrap/app.php` (Laravel 11+):

```php
->withMiddleware(function (Middleware $middleware) {
    $middleware->append(\App\Http\Middleware\AccessLog::class);
})
```

Or for older Laravel versions, add to `$middleware` in `app/Http/Kernel.php`.
