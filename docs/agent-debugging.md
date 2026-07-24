# Debugging Unexpected Exceptions (for AI agents)

Runbook for pulling the browser requests a site served in a given time window, so a reported
failure can be traced to the request that caused it. You are told the site and roughly what
broke; this is how you get the evidence. Everything here is a read-only `GET` — no access to
the target host is required.

```
BASE=https://upmon.r-mulyadi.com/api/v1
KEY=$(rpass get sgtent/upmon/api-key-reed)     # never echo this
curl -s -H "Authorization: Bearer $KEY" "$BASE/..."
```

That key reaches every project. Pass it as a header, never in the URL.

## Pull the requests

`GET /access-logs/sites/{project_id}/{site_key}/logs`

`project_id` and `site_key` are the ids you were given, e.g. `simetris` / `prod`.

| param | notes |
|---|---|
| `start_time` | required, inclusive, ISO-8601 |
| `end` | optional, exclusive |
| `exception_type` | `none` \| `expected` \| `unexpected` |
| `os`, `client_type`, `method` | exact match |
| `order_by` | `epoch_sec` (default), `method`, `path`, `status_code`, `duration_ms` |
| `order_dir` | `desc` (default) \| `asc` |
| `limit` | default 100, max 1000 |
| `start_id` | pagination cursor — do not construct it by hand, follow `next` |

```bash
curl -s -H "Authorization: Bearer $KEY" \
  "$BASE/access-logs/sites/simetris/prod/logs?start_time=2026-07-17T02:55:11Z&exception_type=unexpected&order_dir=desc"
```

**Always send an explicit UTC offset or `Z`.** A naive timestamp is interpreted in the
*backend host's* timezone, which will silently shift your window. When the report is in local
time, convert it: "around 10:00 WIB today" → `start_time=2026-07-24T09:55:00+07:00` and
`end=2026-07-24T10:05:00+07:00`.

Only `exception_type`, `os`, `client_type`, and `method` are filterable server-side. To find
one user's request or one endpoint, take a tight window and filter the rows locally on
`path` / `user_id` / `status_code`.

### Pagination

The response is `{"columns": [...], "rows": [[...]], "next": "<relative url>|null"}`.
`next` repeats the window, filters, ordering, and `limit`, and adds `start_id` set to the
last row's id. Follow it verbatim against the same base URL until it is `null`:

```bash
next="/api/v1/access-logs/sites/simetris/prod/logs?start_time=...&limit=100"
while [ -n "$next" ]; do
  page=$(curl -s -H "Authorization: Bearer $KEY" "https://upmon.r-mulyadi.com$next")
  # ... process rows ...
  next=$(printf '%s' "$page" | jq -r '.next // ""')
done
```

`start_time` still bounds every page, so paging never escapes the window you asked for.
`next` is `null` as soon as a page comes back shorter than `limit`; when the total is an
exact multiple of `limit` you get one final empty page instead.

## Read a row

`columns` + `rows` is a compact table, not objects — zip them:

```python
import json, subprocess, urllib.request
key = subprocess.run(["rpass","get","sgtent/upmon/api-key-reed"], capture_output=True, text=True).stdout.strip()
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
d = json.load(urllib.request.urlopen(req))
rows = [dict(zip(d["columns"], r)) for r in d["rows"]]
```

Columns are the raw access-log schema (`backend/scripts/upmon-agent/CLAUDE.md`). The fields
that matter for triage:

- `epoch_sec` — Unix seconds, UTC. `path`, `method`, `status_code`, `duration_ms`, `user_id`
  identify the request.
- `body`, `query`, `files` — the sanitized request payload, usually enough to reproduce.
  Already JSON-decoded by the backend, so they arrive as objects, not strings.
- `exception_class`, `exception_message` — group by these first.
- `exception_traceback` — a **list** of frames, innermost first (also pre-decoded). The first
  frame outside the framework's vendor directory is usually the bug.
- `exception_is_unexpected` — `null` no exception, `0` expected (validation, 404), `1`
  unexpected, i.e. a real bug.
- `os`, `client_type`, `user_agent` — which browser the user was on.

## Optional: confirm the count first

`GET /access-logs/sites/{project_id}/{site_key}/stats?start_time=<iso>&end=<iso>` returns the
`none` / `expected` / `unexpected` split for the window plus `method` / `os` / `client_type`
distributions. Worth one call when you want to know how many rows you are about to page
through, or which filter values actually exist in that window.

```
'exception_distribution': [['expected', 965], ['none', 100183], ['unexpected', 12]]
```

Note the distributions are computed over the time window **ignoring** your
`exception_type`/`os`/`client_type`/`method` filters, while `summary` and `volume` honor them.

## Worked example

Twelve unexpected exceptions on `simetris/prod` in one week:

```
ErrorException: Undefined array key 0   POST /t/2026/kinerja/save   500   ×7
ErrorException: ...                     POST /t/2026/adk/upload     500   ×5
```

Traceback frame 2 pointed straight at `app/Http/Controllers/KinerjaController.php(322)` in
`validateSave()`, called from `save()` at line 262 — everything above it was Laravel vendor
code. Two endpoints, one controller, twelve requests: enough to open the file and fix it
without touching the server.

The useful shape of a triage pass: count by `(exception_class, exception_message, path)`,
then read one full traceback per group rather than all of them.

## Gotchas

- **Naive timestamps shift the window.** See above — always send `Z` or an offset.
- **Retention.** The agent deletes rows older than the site's `retention_days` (default 360),
  so old windows may be legitimately empty rather than error-free.
- **Sorting by a nullable column.** `status_code` can be `NULL` (request died before a
  response). Paging with `order_by=status_code` drops those rows after the first page. Sort by
  `epoch_sec` when completeness matters.
- **A cursor row can be deleted** by cleanup between pages; that returns an empty page rather
  than an error. Re-issue the query with a fresh window if you hit one unexpectedly.
- **Request bodies contain real user data.** Do not paste raw `body`, `client_ip`, or
  `user_id` values into commits, issues, or shared summaries; quote the exception and the code
  path instead.
