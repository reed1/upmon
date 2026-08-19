#!/usr/bin/env python3
# Managed by Ansible. Do not edit directly — redeploy to update.

import json
import os
import sqlite3
import sys
import time
from base64 import b64decode

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

SITES = CONFIG["sites"]
SITES_BY_KEY = {site["api_key"]: site for site in SITES}


def respond(result=None, error=None):
    print(json.dumps({"error": error, "result": result}))
    sys.exit(0)


def _execute(cursor, sql, bindings=None):
    cursor.execute(sql, bindings or [])
    columns = [desc[0] for desc in cursor.description]
    rows = [list(row) for row in cursor.fetchall()]
    return {"columns": columns, "rows": rows}


def _table_exists(cursor, table):
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", [table])
    return cursor.fetchone() is not None


def _time_conditions(start_time, end):
    conditions = ["epoch_sec >= ?"]
    bindings = [start_time]
    if end is not None:
        conditions.append("epoch_sec < ?")
        bindings.append(end)
    return conditions, bindings


def _filter_conditions(params):
    conditions, bindings = _time_conditions(params["start_time"], params.get("end"))

    exception_type = params.get("exception_type")
    if exception_type == "none":
        conditions.append("exception_is_unexpected IS NULL")
    elif exception_type == "expected":
        conditions.append("exception_is_unexpected = 0")
    elif exception_type == "unexpected":
        conditions.append("exception_is_unexpected = 1")

    for col in ("os", "client_type", "method"):
        if params.get(col) is not None:
            conditions.append(f"{col} = ?")
            bindings.append(params[col])

    return conditions, bindings


# Maps an allowed order_by column to the SQL expression to sort by. Nullable
# columns are coalesced: a NULL on either side of the keyset row-value comparison
# makes it evaluate to NULL, which drops those rows from every page after the
# first and ends paging early when the cursor row itself is NULL.
_LOGS_ORDER_COLUMNS = {
    "epoch_sec": "epoch_sec",
    "method": "method",
    "path": "path",
    "status_code": "IFNULL(status_code, -1)",
    "duration_ms": "duration_ms",
}
_LOGS_MAX_LIMIT = 1000


def _paged_query(cursor, table, params, order_columns, conditions, bindings):
    order_by = params.get("order_by", "epoch_sec")
    if order_by not in order_columns:
        respond(error=f"Invalid order_by: {order_by}")
    sort = order_columns[order_by]
    ascending = params.get("order_dir") == "asc"
    direction = "ASC" if ascending else "DESC"

    start_id = params.get("start_id")
    if start_id is not None:
        # Row-value comparison against the cursor row keeps the keyset stable for
        # any order_by column, with id breaking ties.
        operator = ">" if ascending else "<"
        conditions.append(f"({sort}, id) {operator} (SELECT {sort}, id FROM {table} WHERE id = ?)")
        bindings.append(start_id)

    limit = min(int(params.get("limit") or 100), _LOGS_MAX_LIMIT)

    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM {table} {where} ORDER BY {sort} {direction}, id {direction} LIMIT ?"
    return _execute(cursor, sql, bindings + [limit])


def view_logs(cursor, params):
    conditions, bindings = _filter_conditions(params)
    return _paged_query(cursor, "access_log", params, _LOGS_ORDER_COLUMNS, conditions, bindings)


def _bucket_format(span_minutes):
    if span_minutes < 180:
        return "%Y-%m-%dT%H:%M:00"
    if span_minutes < 4320:
        return "%Y-%m-%dT%H:00:00"
    return "%Y-%m-%dT00:00:00"


def view_stats(cursor, params):
    time_conditions, time_bindings = _time_conditions(params["start_time"], params.get("end"))
    time_where = f"WHERE {' AND '.join(time_conditions)}"

    filtered_conditions, filtered_bindings = _filter_conditions(params)
    filtered_where = f"WHERE {' AND '.join(filtered_conditions)}"

    summary = _execute(
        cursor,
        f"""
        SELECT
            COUNT(*) AS total_requests,
            ROUND(AVG(duration_ms), 2) AS avg_duration_ms,
            ROUND(MIN(duration_ms), 2) AS min_duration_ms,
            ROUND(MAX(duration_ms), 2) AS max_duration_ms,
            SUM(CASE WHEN exception_class IS NOT NULL THEN 1 ELSE 0 END) AS total_exceptions
        FROM access_log {filtered_where}
    """,
        filtered_bindings,
    )

    distributions = _execute(
        cursor,
        f"""
        WITH base AS (
            SELECT * FROM access_log {time_where}
        )
        SELECT 'exception_type' AS dist,
            CASE
                WHEN exception_is_unexpected IS NULL THEN 'none'
                WHEN exception_is_unexpected = 0 THEN 'expected'
                ELSE 'unexpected'
            END AS value,
            COUNT(*) AS count
        FROM base
        GROUP BY value

        UNION ALL
        SELECT 'method', method, COUNT(*)
        FROM base
        GROUP BY method

        UNION ALL
        SELECT 'os', os, COUNT(*)
        FROM base
        GROUP BY os

        UNION ALL
        SELECT 'client_type', client_type, COUNT(*)
        FROM base
        GROUP BY client_type
    """,
        time_bindings,
    )

    end = params.get("end") or int(time.time())
    span_minutes = (end - params["start_time"]) / 60
    bucket_fmt = _bucket_format(span_minutes)

    volume = _execute(
        cursor,
        f"""
        WITH buckets AS (
            SELECT
                strftime('{bucket_fmt}', epoch_sec, 'unixepoch') AS bucket,
                COUNT(*) AS total,
                SUM(exception_class IS NOT NULL) AS exception
            FROM access_log {filtered_where}
            GROUP BY bucket
        )
        SELECT bucket, total - exception AS ok, exception
        FROM buckets
        ORDER BY bucket
    """,
        filtered_bindings,
    )

    return {
        "summary": summary,
        "distributions": distributions,
        "volume": volume,
    }


def view_error_count(cursor, params):
    conditions, bindings = _time_conditions(params["start_time"], params.get("end"))
    conditions.append("exception_is_unexpected = 1")
    where = f"WHERE {' AND '.join(conditions)}"
    return _execute(cursor, f"SELECT COUNT(*) AS error_count FROM access_log {where}", bindings)


_FRONTEND_ERROR_TABLE = "frontend_error"
_FRONTEND_ERROR_ORDER_COLUMNS = {
    "epoch_sec": "epoch_sec",
    "kind": "kind",
    "error_class": "IFNULL(error_class, '')",
    "page_url": "page_url",
}


def _empty_result():
    return {"columns": [], "rows": []}


def _frontend_filter_conditions(params):
    conditions, bindings = _time_conditions(params["start_time"], params.get("end"))

    for col in ("kind", "os", "client_type", "fingerprint", "session_id"):
        if params.get(col) is not None:
            conditions.append(f"{col} = ?")
            bindings.append(params[col])

    return conditions, bindings


def view_frontend_errors(cursor, params):
    if not _table_exists(cursor, _FRONTEND_ERROR_TABLE):
        return _empty_result()

    conditions, bindings = _frontend_filter_conditions(params)
    return _paged_query(
        cursor,
        _FRONTEND_ERROR_TABLE,
        params,
        _FRONTEND_ERROR_ORDER_COLUMNS,
        conditions,
        bindings,
    )


def view_frontend_error_stats(cursor, params):
    if not _table_exists(cursor, _FRONTEND_ERROR_TABLE):
        return {
            "summary": _empty_result(),
            "distributions": _empty_result(),
            "volume": _empty_result(),
            "top_errors": _empty_result(),
        }

    time_conditions, time_bindings = _time_conditions(params["start_time"], params.get("end"))
    time_where = f"WHERE {' AND '.join(time_conditions)}"

    filtered_conditions, filtered_bindings = _frontend_filter_conditions(params)
    filtered_where = f"WHERE {' AND '.join(filtered_conditions)}"

    summary = _execute(
        cursor,
        f"""
        SELECT
            COUNT(*) AS total_errors,
            COUNT(DISTINCT fingerprint) AS distinct_errors,
            COUNT(DISTINCT session_id) AS affected_sessions
        FROM frontend_error {filtered_where}
    """,
        filtered_bindings,
    )

    distributions = _execute(
        cursor,
        f"""
        WITH base AS (
            SELECT * FROM frontend_error {time_where}
        )
        SELECT 'kind' AS dist, kind AS value, COUNT(*) AS count
        FROM base
        GROUP BY value

        UNION ALL
        SELECT 'error_class', error_class, COUNT(*)
        FROM base
        GROUP BY error_class

        UNION ALL
        SELECT 'os', os, COUNT(*)
        FROM base
        GROUP BY os

        UNION ALL
        SELECT 'client_type', client_type, COUNT(*)
        FROM base
        GROUP BY client_type
    """,
        time_bindings,
    )

    end = params.get("end") or int(time.time())
    span_minutes = (end - params["start_time"]) / 60
    bucket_fmt = _bucket_format(span_minutes)

    volume = _execute(
        cursor,
        f"""
        SELECT
            strftime('{bucket_fmt}', epoch_sec, 'unixepoch') AS bucket,
            COUNT(*) AS errors
        FROM frontend_error {filtered_where}
        GROUP BY bucket
        ORDER BY bucket
    """,
        filtered_bindings,
    )

    # SQLite fills bare columns from the row that produced MAX(epoch_sec), so each
    # group carries the details of its most recent occurrence.
    top_errors = _execute(
        cursor,
        f"""
        SELECT
            fingerprint,
            error_class,
            message,
            kind,
            page_url,
            COUNT(*) AS count,
            COUNT(DISTINCT session_id) AS sessions,
            MAX(epoch_sec) AS last_seen
        FROM frontend_error {filtered_where}
        GROUP BY fingerprint
        ORDER BY count DESC
        LIMIT 20
    """,
        filtered_bindings,
    )

    return {
        "summary": summary,
        "distributions": distributions,
        "volume": volume,
        "top_errors": top_errors,
    }


def view_frontend_error_count(cursor, params):
    if not _table_exists(cursor, _FRONTEND_ERROR_TABLE):
        return {"columns": ["error_count"], "rows": [[None]]}

    conditions, bindings = _time_conditions(params["start_time"], params.get("end"))
    where = f"WHERE {' AND '.join(conditions)}"
    return _execute(cursor, f"SELECT COUNT(*) AS error_count FROM frontend_error {where}", bindings)


VIEWS = {
    "logs": view_logs,
    "stats": view_stats,
    "error_count": view_error_count,
    "frontend_errors": view_frontend_errors,
    "frontend_error_stats": view_frontend_error_stats,
    "frontend_error_count": view_frontend_error_count,
}


def _parse_params():
    raw = json.loads(sys.argv[1])
    return json.loads(b64decode(raw["q"]).decode())


def cmd_query(params):
    api_key = params.get("api_key")
    if api_key not in SITES_BY_KEY:
        respond(error="Unauthorized")

    site = SITES_BY_KEY[api_key]

    view_name = params.get("view")
    if view_name not in VIEWS:
        respond(error=f"Unknown view: {view_name}")

    conn = sqlite3.connect(f"file:{site['db_path']}?mode=ro", uri=True)
    try:
        result = VIEWS[view_name](conn.cursor(), params)
        respond(result=result)
    finally:
        conn.close()


def cmd_cleanup(params):
    api_key = params.get("api_key")
    if api_key not in SITES_BY_KEY:
        respond(error="Unauthorized")

    retention_days = params.get("retention_days")
    if retention_days is None:
        respond(error="Missing required field: retention_days")

    site = SITES_BY_KEY[api_key]
    db_path = site["db_path"]

    if not os.path.exists(db_path):
        respond(error=f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cutoff = [f"-{retention_days} days"]
        cursor.execute(
            "DELETE FROM access_log WHERE epoch_sec < CAST(strftime('%s', 'now', ?) AS INTEGER)",
            cutoff,
        )
        deleted = cursor.rowcount

        # Sites adopt frontend_error on their own schedule; a host without it must
        # still get its access_log pruned.
        frontend_deleted = None
        if _table_exists(cursor, _FRONTEND_ERROR_TABLE):
            cursor.execute(
                "DELETE FROM frontend_error WHERE epoch_sec < CAST(strftime('%s', 'now', ?) AS INTEGER)",
                cutoff,
            )
            frontend_deleted = cursor.rowcount

        cursor.execute("PRAGMA incremental_vacuum")
        conn.commit()
        respond(result={"deleted": deleted, "frontend_deleted": frontend_deleted})
    finally:
        conn.close()


def main():
    params = _parse_params()
    command = params["command"]

    if command == "query":
        cmd_query(params)
    elif command == "cleanup":
        cmd_cleanup(params)
    else:
        respond(error=f"Unexpected command: {command}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        respond(error=f"{type(e).__name__}: {e}")
