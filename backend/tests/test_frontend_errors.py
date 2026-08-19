import json

import pytest
from httpx import ASGITransport, AsyncClient

from upmon_backend import access
from upmon_backend.access import derive_api_key
from upmon_backend.config import Settings
from upmon_backend.main import create_app
from upmon_backend.routes import agent_frontend_errors, agent_logs

SECRET = "test-secret"
ADMIN_EMAIL = "admin@b.com"
VIEWER_EMAIL = "viewer@b.com"
LOGS_PATH = "/api/v1/frontend-errors/sites/proj/site/logs"
STATS_PATH = "/api/v1/frontend-errors/sites/proj/site/stats"
START = "start_time=2026-06-24T02:17:07%2B00:00"
COLUMNS = ["id", "epoch_sec", "kind", "error_class", "message", "fingerprint"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "_cache", access._AccessCache())
    monkeypatch.setattr(agent_logs, "_cache", agent_logs._AgentConfigCache())
    users = tmp_path / "users.yaml"
    users.write_text(
        f"users:\n"
        f"  - email: {ADMIN_EMAIL}\n    role: admin\n"
        f"  - email: {VIEWER_EMAIL}\n    role: viewer\n    project_ids: [other]\n"
    )
    agents = tmp_path / "agents.json"
    agents.write_text(
        json.dumps(
            {
                "sites": [
                    {
                        "project_id": "proj",
                        "site_key": "site",
                        "agent_url": "http://agent.invalid/health/agent",
                        "agent_api_key": "agent-key",
                    }
                ]
            }
        )
    )
    settings = Settings(
        database_url="postgres://fake:fake@localhost/fake",
        api_key_secret=SECRET,
        frontend_dir="/tmp",
        users_config=str(users),
        agent_config=str(agents),
        dev_identity_email=None,
    )
    return create_app(settings)


@pytest.fixture
def sent(monkeypatch):
    """Captures the payload sent to the agent and returns `rows` many canned rows."""
    captured = {}

    async def fake_query_agent(site, view, params):
        captured["view"] = view
        captured["params"] = params
        if view == "frontend_error_stats":
            return {
                "summary": {"columns": ["total_errors"], "rows": [[7]]},
                "distributions": {
                    "columns": ["dist", "value", "count"],
                    "rows": [
                        ["kind", "error", 5],
                        ["kind", "manual", 2],
                        ["error_class", "TypeError", 7],
                        ["os", None, 1],
                        ["client_type", "browser", 7],
                    ],
                },
                "volume": {"columns": ["bucket", "errors"], "rows": []},
                "top_errors": {"columns": ["fingerprint"], "rows": [["fp1"]]},
            }
        count = captured.get("rows", 0)
        first = params.get("start_id") or 0
        return {
            "columns": COLUMNS,
            "rows": [
                [first + i + 1, 1700, "error", "TypeError", "boom", "fp1"] for i in range(count)
            ],
        }

    monkeypatch.setattr(agent_frontend_errors, "_query_agent", fake_query_agent)
    return captured


async def _get(app, path, email=ADMIN_EMAIL, headers=None):
    if headers is None:
        headers = {"authorization": f"Bearer {derive_api_key(SECRET, email)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path, headers=headers)


async def test_logs_dispatches_frontend_errors_view(app, sent):
    sent["rows"] = 1
    resp = await _get(app, f"{LOGS_PATH}?{START}")
    assert resp.status_code == 200
    assert sent["view"] == "frontend_errors"
    assert sent["params"]["start_time"] == 1782267427
    assert sent["params"]["limit"] == 100
    assert sent["params"]["start_id"] is None


async def test_stats_dispatches_stats_view(app, sent):
    resp = await _get(app, f"{STATS_PATH}?{START}&kind=unhandledrejection")
    assert resp.status_code == 200
    assert sent["view"] == "frontend_error_stats"
    assert sent["params"]["kind"] == "unhandledrejection"

    body = resp.json()
    assert body["summary"]["rows"] == [[7]]
    assert body["top_errors"]["rows"] == [["fp1"]]
    # highest count first, and the null os bucket is dropped
    assert body["kind_distribution"]["rows"] == [["error", 5], ["manual", 2]]
    assert body["error_class_distribution"]["rows"] == [["TypeError", 7]]
    assert body["os_distribution"]["rows"] == []


async def test_frontend_filters_are_forwarded(app, sent):
    sent["rows"] = 0
    await _get(app, f"{LOGS_PATH}?{START}&kind=error&fingerprint=a1b2c3d4&session_id=s-1&os=linux")
    params = sent["params"]
    assert params["kind"] == "error"
    assert params["fingerprint"] == "a1b2c3d4"
    assert params["session_id"] == "s-1"
    assert params["os"] == "linux"


async def test_short_page_has_no_next(app, sent):
    sent["rows"] = 3
    assert (await _get(app, f"{LOGS_PATH}?{START}&limit=5")).json()["next"] is None


async def test_full_page_next_carries_filters_and_cursor(app, sent):
    sent["rows"] = 5
    next_url = (await _get(app, f"{LOGS_PATH}?{START}&kind=error&limit=5")).json()["next"]

    assert next_url.startswith(f"{LOGS_PATH}?")
    assert (await _get(app, next_url)).status_code == 200
    params = sent["params"]
    assert params["start_id"] == 5
    assert params["limit"] == 5
    assert params["start_time"] == 1782267427
    assert params["kind"] == "error"


async def test_unadopted_site_returns_empty_page(app, sent):
    """The agent returns an empty result for sites without a frontend_error table."""
    sent["rows"] = 0
    resp = await _get(app, f"{LOGS_PATH}?{START}")
    assert resp.status_code == 200
    assert resp.json() == {"columns": COLUMNS, "rows": [], "next": None}


async def test_requires_api_key(app, sent):
    assert (await _get(app, f"{LOGS_PATH}?{START}", headers={})).status_code == 401


async def test_viewer_without_project_access_is_forbidden(app, sent):
    assert (await _get(app, f"{LOGS_PATH}?{START}", email=VIEWER_EMAIL)).status_code == 403
    assert (await _get(app, f"{STATS_PATH}?{START}", email=VIEWER_EMAIL)).status_code == 403


async def test_unknown_site_is_404(app, sent):
    resp = await _get(app, f"/api/v1/frontend-errors/sites/proj/nope/logs?{START}")
    assert resp.status_code == 404


async def test_limit_is_bounded(app, sent):
    sent["rows"] = 0
    assert (await _get(app, f"{LOGS_PATH}?{START}&limit=1001")).status_code == 422
    assert (await _get(app, f"{LOGS_PATH}?{START}&limit=0")).status_code == 422
