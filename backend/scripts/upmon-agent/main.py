#!/usr/bin/env python3
# Managed by Ansible. Do not edit directly — redeploy to update.
#
# upmon-agent: Access log query tool.
# Usage: python3 main.py '<json_args>'
#
# json_args keys:
#   api_key    — authentication key (required)
#   db_path    — path to SQLite database (required)
#   query      — query name: "logs" or "stats" (required)
#   params     — query-specific parameters (optional, default {})

import json
import sqlite3
import sys

# {{ ansible_managed }}
API_KEY = "{{ upmon_agent_api_key }}"

MAX_LIMIT = 1000
DEFAULT_LIMIT = 100


def respond(result=None, error=None):
    print(json.dumps({"error": error, "result": result}))
    if error:
        sys.exit(1)


def query_logs(cursor, params):
    conditions = []
    bindings = []

    if "path" in params:
        conditions.append("path = ?")
        bindings.append(params["path"])
    if "method" in params:
        conditions.append("method = ?")
        bindings.append(params["method"])
    if "status_code" in params:
        conditions.append("status_code = ?")
        bindings.append(int(params["status_code"]))
    if "min_duration_ms" in params:
        conditions.append("duration_ms >= ?")
        bindings.append(float(params["min_duration_ms"]))
    if "has_exception" in params:
        if params["has_exception"] in ("true", "1", True):
            conditions.append("exception_class IS NOT NULL")
        else:
            conditions.append("exception_class IS NULL")

    limit = min(int(params.get("limit", DEFAULT_LIMIT)), MAX_LIMIT)
    offset = int(params.get("offset", 0))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM access_logs {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    bindings.extend([limit, offset])

    cursor.execute(sql, bindings)
    columns = [desc[0] for desc in cursor.description]
    rows = [list(row) for row in cursor.fetchall()]
    return {"columns": columns, "rows": rows}


def query_stats(cursor, params):
    conditions = []
    bindings = []

    if "path" in params:
        conditions.append("path = ?")
        bindings.append(params["path"])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_requests,
            ROUND(AVG(duration_ms), 2) AS avg_duration_ms,
            ROUND(MIN(duration_ms), 2) AS min_duration_ms,
            ROUND(MAX(duration_ms), 2) AS max_duration_ms,
            SUM(CASE WHEN exception_class IS NOT NULL THEN 1 ELSE 0 END) AS total_exceptions
        FROM access_logs {where}
        """,
        bindings,
    )
    summary_columns = [desc[0] for desc in cursor.description]
    summary_rows = [list(row) for row in cursor.fetchall()]

    cursor.execute(
        f"""
        SELECT status_code, COUNT(*) AS count
        FROM access_logs {where}
        GROUP BY status_code
        ORDER BY status_code
        """,
        bindings,
    )
    dist_columns = [desc[0] for desc in cursor.description]
    dist_rows = [list(row) for row in cursor.fetchall()]

    return {
        "summary": {"columns": summary_columns, "rows": summary_rows},
        "status_distribution": {"columns": dist_columns, "rows": dist_rows},
    }


QUERIES = {
    "logs": query_logs,
    "stats": query_stats,
}


def main():
    if len(sys.argv) != 2:
        respond(error="Usage: python3 main.py '<json_args>'")

    args = json.loads(sys.argv[1])

    if args.get("api_key") != API_KEY:
        respond(error="Unauthorized")

    db_path = args.get("db_path")
    query_name = args.get("query")
    params = args.get("params", {})

    if not db_path or not query_name:
        respond(error="Missing required fields: db_path, query")

    if query_name not in QUERIES:
        respond(error=f"Unknown query: {query_name}. Available: {', '.join(QUERIES)}")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        respond(result=QUERIES[query_name](cursor, params))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
