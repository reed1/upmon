"""Keyset paging in the agent script, exercised against a real SQLite database.

The route tests stub `_query_agent`, so the agent's SQL is otherwise untested.
"""

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

AGENT_MAIN = Path(__file__).parents[1] / "scripts" / "upmon-agent" / "main.py"


@pytest.fixture(scope="module")
def agent(tmp_path_factory):
    """Loads the agent script, which reads config.json next to itself at import."""
    src = tmp_path_factory.mktemp("agent") / "agent_main.py"
    src.write_text(AGENT_MAIN.read_text())
    (src.parent / "config.json").write_text(json.dumps({"sites": []}))

    spec = importlib.util.spec_from_file_location("agent_main", src)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cursor():
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, epoch_sec INTEGER NOT NULL,
            method TEXT NOT NULL, path TEXT NOT NULL, status_code INTEGER,
            duration_ms REAL NOT NULL, client_type TEXT NOT NULL,
            exception_class TEXT, exception_is_unexpected INTEGER
        )
    """
    )
    c.execute(
        """
        CREATE TABLE frontend_error (
            id INTEGER PRIMARY KEY AUTOINCREMENT, epoch_sec INTEGER NOT NULL,
            kind TEXT NOT NULL, error_class TEXT, message TEXT NOT NULL,
            page_url TEXT NOT NULL, fingerprint TEXT NOT NULL, session_id TEXT,
            os TEXT, client_type TEXT NOT NULL
        )
    """
    )
    yield c
    conn.close()


def _insert_frontend_errors(cursor, error_classes):
    for i, error_class in enumerate(error_classes):
        cursor.execute(
            """INSERT INTO frontend_error
               (epoch_sec, kind, error_class, message, page_url, fingerprint, client_type)
               VALUES (?, 'error', ?, 'boom', '/p', ?, 'browser')""",
            (1700 + i, error_class, f"fp{i}"),
        )


def _page_through(view, cursor, column, order_dir, limit=2):
    """Walks every page the way the SPA does, returning (id, sort value) pairs."""
    collected = []
    start_id = None
    while True:
        result = view(
            cursor,
            {
                "start_time": 0,
                "order_by": column,
                "order_dir": order_dir,
                "limit": limit,
                "start_id": start_id,
            },
        )
        rows = result["rows"]
        id_index = result["columns"].index("id")
        value_index = result["columns"].index(column)
        collected += [(r[id_index], r[value_index]) for r in rows]
        if len(rows) < limit:
            return collected
        start_id = rows[-1][id_index]


# A NULL sort column makes the keyset row-value comparison evaluate to NULL, which
# silently drops those rows from later pages unless the column is coalesced.
@pytest.mark.parametrize("order_dir", ["desc", "asc"])
def test_frontend_error_paging_keeps_null_error_class(agent, cursor, order_dir):
    _insert_frontend_errors(cursor, ["TypeError", None, "RangeError", None, "AError", None])

    paged = _page_through(agent.view_frontend_errors, cursor, "error_class", order_dir)

    assert sorted(id for id, _ in paged) == [1, 2, 3, 4, 5, 6]
    values = [value for _, value in paged]
    assert values == sorted(
        values, key=lambda v: (v is not None, v or ""), reverse=order_dir == "desc"
    )


def test_access_log_paging_keeps_null_status_code(agent, cursor):
    for i, status_code in enumerate([200, None, 500, None, 404]):
        cursor.execute(
            """INSERT INTO access_log
               (epoch_sec, method, path, status_code, duration_ms, client_type)
               VALUES (?, 'GET', '/', ?, 1.0, 'browser')""",
            (1700 + i, status_code),
        )

    paged = _page_through(agent.view_logs, cursor, "status_code", "desc")

    assert [id for id, _ in paged] == [3, 5, 1, 4, 2]


def test_frontend_views_tolerate_a_missing_table(agent, cursor):
    cursor.execute("DROP TABLE frontend_error")
    params = {"start_time": 0}

    assert agent.view_frontend_errors(cursor, params) == {"columns": [], "rows": []}
    assert agent.view_frontend_error_count(cursor, params)["rows"] == [[None]]
    assert agent.view_frontend_error_stats(cursor, params)["top_errors"]["rows"] == []


def test_invalid_order_by_is_rejected(agent, cursor):
    with pytest.raises(SystemExit):
        agent.view_frontend_errors(cursor, {"start_time": 0, "order_by": "message"})
