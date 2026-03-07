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
    if error:
        sys.exit(1)


def _execute(cursor, sql, bindings=None):
    cursor.execute(sql, bindings or [])
    columns = [desc[0] for desc in cursor.description]
    rows = [list(row) for row in cursor.fetchall()]
    return {"columns": columns, "rows": rows}


def _time_conditions(start, end):
    conditions = ["epoch_sec >= ?"]
    bindings = [start]
    if end is not None:
        conditions.append("epoch_sec <= ?")
        bindings.append(end)
    return conditions, bindings


def _filter_conditions(params):
    conditions, bindings = _time_conditions(params["start"], params.get("end"))

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


_LOGS_ORDER_COLUMNS = {"epoch_sec", "method", "path", "status_code", "duration_ms"}


def view_logs(cursor, params):
    conditions, bindings = _filter_conditions(params)

    order_by = params.get("order_by", "epoch_sec")
    if order_by not in _LOGS_ORDER_COLUMNS:
        respond(error=f"Invalid order_by: {order_by}")
    direction = "ASC" if params.get("order_dir") == "asc" else "DESC"

    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM access_log {where} ORDER BY {order_by} {direction} LIMIT 100"
    return _execute(cursor, sql, bindings)


def _bucket_format(span_minutes):
    if span_minutes < 180:
        return "%Y-%m-%dT%H:%M:00"
    if span_minutes < 4320:
        return "%Y-%m-%dT%H:00:00"
    return "%Y-%m-%dT00:00:00"


def view_stats(cursor, params):
    time_conditions, time_bindings = _time_conditions(params["start"], params.get("end"))
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
    span_minutes = (end - params["start"]) / 60
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


VIEWS = {
    "logs": view_logs,
    "stats": view_stats,
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
        cursor.execute(
            "DELETE FROM access_log WHERE epoch_sec < CAST(strftime('%s', 'now', ?) AS INTEGER)",
            [f"-{retention_days} days"],
        )
        deleted = cursor.rowcount
        cursor.execute("PRAGMA incremental_vacuum")
        conn.commit()
        respond(result={"deleted": deleted})
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
        raise RuntimeError(f"Unexpected command: {command}")


if __name__ == "__main__":
    main()
