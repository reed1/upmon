#!/usr/bin/env python3
# Managed by Ansible. Do not edit directly — redeploy to update.

# upmon-agent: Read-only SQL proxy for access log queries.
# Usage: python3 main.py '<json_args>'
#
# json_args keys:
#   api_key    — authentication key (required)
#   db_path    — path to SQLite database (required)
#   sql        — SQL query to execute (required)
#   bindings   — query parameter bindings (optional, default [])

import json
import os
import sqlite3
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(CONFIG_PATH) as f:
    API_KEYS = json.load(f)["api_keys"]


def respond(result=None, error=None):
    print(json.dumps({"error": error, "result": result}))
    if error:
        sys.exit(1)


def main():
    if len(sys.argv) != 2:
        respond(error="Usage: python3 main.py '<json_args>'")

    args = json.loads(sys.argv[1])

    if args.get("api_key") not in API_KEYS:
        respond(error="Unauthorized")

    db_path = args.get("db_path")
    sql = args.get("sql")

    if not db_path or not sql:
        respond(error="Missing required fields: db_path, sql")

    bindings = args.get("bindings", [])
    if isinstance(bindings, str):
        bindings = json.loads(bindings)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, bindings)
        columns = [desc[0] for desc in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        respond(result={"columns": columns, "rows": rows})
    finally:
        conn.close()


if __name__ == "__main__":
    main()
