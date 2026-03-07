# 0001: Rename `platform` to `os`, enforce `client_type` NOT NULL

Renames the `platform` column to `os` in the access_log SQLite database and ensures `client_type` is never null.

## Why

The old `platform` column mixed OS names (`android`, `ios`) with a channel name (`web`). The new `os` column stores the actual operating system: `android`, `ios`, `windows`, `macos`, `linux`, or null.

`client_type` (`app` or `browser`) distinguishes native apps from browsers. It was previously nullable — now defaults to `browser` when no `X-Client-Type` header is present.

## Changes required

### 1. Frontend (client-side headers)

Replace the old headers:

```
X-Platform: <capacitor platform>   // REMOVE
X-Client-Type: app | browser       // KEEP
```

With:

```
X-Client-Type: app | browser       // always sent
X-OS: android | ios                 // only sent when native app
```

Example (Capacitor):

```ts
headers: {
  'X-Client-Type': Capacitor.isNativePlatform() ? 'app' : 'browser',
  ...(Capacitor.isNativePlatform() && { 'X-OS': Capacitor.getPlatform() }),
}
```

The `X-OS` header is only sent from native apps because Capacitor knows the real OS. For browsers, the backend parses the User-Agent instead.

### 2. Backend (OS detection)

Add a function to determine `os` from the request:

- If `X-Client-Type` is `app`: trust `X-OS` header (Capacitor knows the native OS).
- If `X-Client-Type` is `browser` (or absent, defaulting to `browser`): parse `User-Agent`.

Python example:

```python
def get_client_info(request) -> tuple[str | None, str]:
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
    if "Linux" in ua:
        return "linux"
    return None
```

### 3. Schema change

Update the `CREATE TABLE` statement in the access logger:

```diff
- platform TEXT,
- client_type TEXT,
+ os TEXT,
+ client_type TEXT NOT NULL,
```

### 4. Enforce `client_type` as non-nullable in application code

Ensure the access log entry type uses `string`, not `string | null`, for `client_type`. The detection function must always return a concrete value — defaulting to `"browser"` when no header is present. This guarantees the `NOT NULL` constraint is never violated at insert time.

TypeScript example:

```ts
interface AccessLogEntry {
  os: string | null;
  client_type: string;  // not string | null
}
```

Python example:

```python
@dataclass
class AccessLogEntry:
    os: str | None
    client_type: str  # never None
```

### 5. Run the migration

Stop the service first to avoid writes during migration.

```bash
# Stop the service
systemctl --user stop <service-name>

# Run migration
python migrate.py /path/to/run/access-log/access-log.db

# Start the service
systemctl --user start <service-name>
```

The script will:
1. Back up the database to `~/tmp_access_log_backup_<name>.db`
2. Rename `platform` → `os`
3. Re-parse `os` from `user_agent` for all existing rows
4. Set `client_type = 'browser'` where null
5. Print a summary report of `os` and `client_type` counts

### 6. Verify and clean up

After starting the service, verify that new rows are being written with the correct `os` and `client_type` values. Then remove the backup file printed by the migration script.
