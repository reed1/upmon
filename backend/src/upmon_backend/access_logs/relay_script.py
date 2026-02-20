"""Standalone relay script sent to remote hosts via SSH stdin.

This script uses only the Python stdlib so it can run on any remote machine
with Python 3.10+. It opens a SQLite database in read-only mode and serves
parameterized SELECT queries over a local HTTP interface.

Usage: python3 -u - <port> <db_path>
Prints "RELAY_READY <port>" to stdout when listening.
Exits after 5 minutes of inactivity.
"""

SCRIPT = r'''
import json
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(sys.argv[1])
db_path = sys.argv[2]

IDLE_TIMEOUT = 300

conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

idle_timer = None
server = None
timer_lock = threading.Lock()


def reset_idle_timer():
    global idle_timer
    with timer_lock:
        if idle_timer is not None:
            idle_timer.cancel()
        idle_timer = threading.Timer(IDLE_TIMEOUT, lambda: server.shutdown())
        idle_timer.daemon = True
        idle_timer.start()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        sql = body["sql"]
        params = body.get("params", [])

        stripped = sql.strip().upper()
        if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "only SELECT queries allowed"}).encode())
            return

        reset_idle_timer()

        try:
            cursor = conn.execute(sql, params)
            columns = [d[0] for d in cursor.description]
            rows = [list(row) for row in cursor.fetchall()]
            resp = json.dumps({"columns": columns, "rows": rows})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp.encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())


server = HTTPServer(("127.0.0.1", port), Handler)
reset_idle_timer()
print(f"RELAY_READY {port}", flush=True)
server.serve_forever()
conn.close()
'''
