# Access Log — Laravel with Livewire

Laravel middleware implementation with Livewire/Filament request decoding. Extends the [standard Laravel example](laravel.md) with handling for Livewire's batch update requests, which would otherwise all log as `POST /livewire/update` with opaque payloads.

See [access-log-writing.md](../access-log-writing.md) for schema and rules.

## Differences from Standard Laravel

- **Livewire request decoding** — Livewire sends all interactions as `POST /livewire/update` with a `components` array. The middleware decodes these into readable paths like `livewire:component-name` and extracts the method calls and property updates as the body.
- **Skip internal plumbing** — Livewire/Filament fire many internal methods (`__lazyLoad`, `getTableRecords`, etc.) that aren't meaningful user actions. These are filtered out; if all components in a batch are plumbing, the request is skipped entirely.
- **Truncation** — Livewire payloads can be large (full component snapshots). Values are truncated at depth 3 and strings over 500 chars are clipped.
- **Deep sensitive field matching** — Livewire flattens nested props into dotted keys like `data.password`. Redaction matches both the full key and its last dot-segment.
- **Skip 419 (CSRF expired)** — In addition to 404, unauthenticated 419 responses are skipped (common with Livewire when sessions expire).
- **Skip `AuthenticationException`** — Auth redirects are not logged as exceptions.
- **Try-catch on insert** — Livewire apps tend to have higher request volume; a SQLite failure shouldn't break the response.

## AccessLog Service

Same as the [standard Laravel example](laravel.md#accesslog-service) — no changes needed.

## Middleware

`app/Http/Middleware/AccessLog.php`:

```php
<?php

namespace App\Http\Middleware;

use App\Services\AccessLog as AccessLogService;
use Closure;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Exception\HttpException;

class AccessLog
{
    private const SENSITIVE_FIELDS = [
        'password',
        'password_confirmation',
        'current_password',
        'new_password',
        'new_password_confirmation',
    ];

    /**
     * Internal Livewire/Filament methods that are just UI plumbing,
     * not user-initiated actions worth logging.
     */
    private const LIVEWIRE_IGNORED_METHODS = [
        '__lazyLoad',
        '__dispatch',
        '_finishUpload',
        'callSchemaComponentMethod',
        'getTableRecords',
        'resetTableFiltersForm',
        'loadTableColumnSearchForms',
        'getActiveActionsCountProperty',
    ];

    public function handle(Request $request, Closure $next): Response
    {
        if (
            ! config('yourapp.access_log_enabled')
            || $request->isMethod('OPTIONS')
            || in_array($request->getPathInfo(), ['/up', '/health', '/health/agent'])
        ) {
            return $next($request);
        }

        $data = ['start' => hrtime(true)];

        $response = $next($request);
        $data['status'] = $response->getStatusCode();

        $e = $response->exception ?? null;
        if ($e instanceof AuthenticationException) {
            return $response;
        }
        if ($e) {
            $data['exc_class'] = get_class($e);
            $data['exc_message'] = $e->getMessage();
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

        if ($userId === null && in_array($statusCode, [404, 419])) {
            return;
        }

        $durationMs = round((hrtime(true) - $data['start']) / 1_000_000, 2);
        $forwarded = $request->header('X-Forwarded-For');
        $clientIp = $forwarded ? explode(',', $forwarded)[0] : $request->ip();

        $livewire = self::decodeLivewireRequest($request);

        if ($livewire && ($livewire['skip'] ?? false)) {
            return;
        }

        $path = $livewire ? $livewire['path'] : $request->getPathInfo();
        $queryParams = $request->query();
        $body = $livewire
            ? $livewire['body']
            : (! $request->isMethod('GET') ? self::redactSensitive($request->all()) : null);

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

        try {
            app(AccessLogService::class)->insert([
                'epoch_sec' => time(),
                'client_ip' => $clientIp,
                'method' => $request->method(),
                'path' => $path,
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
        } catch (\Throwable $e) {
            report($e);
        }
    }

    /**
     * Decode Livewire update requests into readable path + body.
     *
     * @return array{path: string, body: array, skip?: bool}|null
     */
    private static function decodeLivewireRequest(Request $request): ?array
    {
        if (! $request->hasHeader('X-Livewire')) {
            return null;
        }

        $components = $request->input('components');
        if (! is_array($components) || empty($components)) {
            return null;
        }

        $decoded = [];
        $firstComponentName = null;

        foreach ($components as $component) {
            $snapshot = json_decode($component['snapshot'] ?? '{}', true);
            $componentName = $snapshot['memo']['name'] ?? 'unknown';
            $firstComponentName ??= $componentName;

            $calls = $component['calls'] ?? [];
            $updates = $component['updates'] ?? [];

            $meaningfulCalls = array_filter($calls, function (array $call) {
                return ! in_array($call['method'] ?? '', self::LIVEWIRE_IGNORED_METHODS);
            });

            if (empty($meaningfulCalls) && empty($updates)) {
                continue;
            }

            $entry = ['component' => $componentName];

            if ($meaningfulCalls) {
                $entry['calls'] = array_values(array_map(fn (array $call) => [
                    'method' => $call['method'] ?? '?',
                    'params' => self::redactSensitive(self::truncateDeep($call['params'] ?? [])),
                ], $meaningfulCalls));
            }

            if ($updates) {
                $entry['updates'] = self::redactSensitive($updates);
            }

            $decoded[] = $entry;
        }

        if (empty($decoded)) {
            return ['skip' => true, 'path' => '', 'body' => []];
        }

        $path = count($decoded) === 1
            ? "livewire:{$firstComponentName}"
            : 'livewire:batch(' . count($decoded) . ')';

        return ['path' => $path, 'body' => $decoded];
    }

    private static function truncateDeep(mixed $value, int $depth = 0): mixed
    {
        if ($depth > 3) {
            return is_array($value) ? '[...]' : $value;
        }

        if (is_string($value) && strlen($value) > 500) {
            return substr($value, 0, 500) . '...[truncated]';
        }

        if (is_array($value)) {
            $result = [];
            $count = 0;
            foreach ($value as $k => $v) {
                if ($count++ >= 20) {
                    $result['...'] = '(' . (count($value) - 20) . ' more)';
                    break;
                }
                $result[$k] = self::truncateDeep($v, $depth + 1);
            }

            return $result;
        }

        return $value;
    }

    private static function redactSensitive(mixed $value): mixed
    {
        if (! is_array($value)) {
            return $value;
        }

        $result = [];
        foreach ($value as $key => $item) {
            if (is_string($key) && self::isSensitiveKey($key)) {
                $result[$key] = '[REDACTED]';

                continue;
            }
            $result[$key] = is_array($item) ? self::redactSensitive($item) : $item;
        }

        return $result;
    }

    /**
     * Match either the exact key or its last dot-segment against SENSITIVE_FIELDS.
     * Livewire flattens nested props into dotted keys like `data.password`.
     */
    private static function isSensitiveKey(string $key): bool
    {
        if (in_array($key, self::SENSITIVE_FIELDS, true)) {
            return true;
        }

        $segments = explode('.', $key);
        $last = end($segments);

        return in_array($last, self::SENSITIVE_FIELDS, true);
    }

    private static function parseOs(?string $ua): ?string
    {
        if (! $ua) {
            return null;
        }
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

## Logged Path Examples

| Request | Logged `path` |
|---|---|
| Normal page load `GET /dashboard` | `/dashboard` |
| Livewire form submit | `livewire:pages.profile.edit-form` |
| Livewire table action + filter in one batch | `livewire:batch(2)` |
| Livewire internal plumbing only (`__lazyLoad`, `getTableRecords`) | *(skipped entirely)* |

## Registering the Middleware

Same as the [standard Laravel example](laravel.md#registering-the-middleware).
