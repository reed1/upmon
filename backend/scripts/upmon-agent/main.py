#!/usr/bin/env python3
# Managed by Ansible. Do not edit directly — redeploy to update.

import argparse
import json
import os
import sqlite3
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

SITES = CONFIG["sites"]
SITES_BY_KEY = {site["api_key"]: site for site in SITES}


def respond(result=None, error=None):
    print(json.dumps({"error": error, "result": result}))
    if error:
        sys.exit(1)


def cmd_query(args):
    parsed = json.loads(args.json_args)

    api_key = parsed.get("api_key")
    if api_key not in SITES_BY_KEY:
        respond(error="Unauthorized")

    site = SITES_BY_KEY[api_key]
    db_path = site["db_path"]
    sql = parsed.get("sql")

    if not sql:
        respond(error="Missing required field: sql")

    bindings = parsed.get("bindings", [])
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


def cmd_cleanup(_args):
    for site in SITES:
        db_path = site["db_path"]
        if not os.path.exists(db_path):
            print(f"Skipping (not found): {db_path}")
            continue

        retention_days = site.get("retention_days", 360)
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
            print(f"Cleaned {db_path}: {deleted} rows deleted")
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(prog="upmon-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("json_args")

    subparsers.add_parser("cleanup")

    args = parser.parse_args()

    if args.command == "query":
        cmd_query(args)
    elif args.command == "cleanup":
        cmd_cleanup(args)
    else:
        raise RuntimeError(f"Unexpected command: {args.command}")


if __name__ == "__main__":
    main()
