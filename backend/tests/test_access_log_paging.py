import json

import pytest
from httpx import ASGITransport, AsyncClient

from upmon_backend import access
from upmon_backend.access import derive_api_key
from upmon_backend.config import Settings
from upmon_backend.main import create_app
from upmon_backend.routes import agent_logs

SECRET = "test-secret"
ADMIN_EMAIL = "admin@b.com"
LOGS_PATH = "/api/v1/access-logs/sites/proj/site/logs"
COLUMNS = ["id", "epoch_sec", "method", "path", "status_code", "duration_ms"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "_cache", access._AccessCache())
    monkeypatch.setattr(agent_logs, "_cache", agent_logs._AgentConfigCache())
    users = tmp_path / "users.yaml"
    users.write_text(f"users:\n  - email: {ADMIN_EMAIL}\n    role: admin\n")
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
        count = captured.get("rows", 0)
        first = params.get("start_id") or 0
        return {
            "columns": COLUMNS,
            "rows": [[first + i + 1, 1700, "GET", "/p", 200, 1.0] for i in range(count)],
        }

    monkeypatch.setattr(agent_logs, "_query_agent", fake_query_agent)
    return captured


async def _get(app, path):
    key = derive_api_key(SECRET, ADMIN_EMAIL)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path, headers={"authorization": f"Bearer {key}"})


async def test_start_time_is_converted_and_defaults_forwarded(app, sent):
    sent["rows"] = 1
    resp = await _get(app, f"{LOGS_PATH}?start_time=2026-06-24T02:17:07%2B00:00")
    assert resp.status_code == 200
    assert sent["params"]["start_time"] == 1782267427
    assert sent["params"]["limit"] == 100
    assert sent["params"]["start_id"] is None


async def test_short_page_has_no_next(app, sent):
    sent["rows"] = 3
    resp = await _get(app, f"{LOGS_PATH}?start_time=2026-06-24T02:17:07%2B00:00&limit=5")
    assert resp.json()["next"] is None


async def test_full_page_next_carries_window_filters_and_cursor(app, sent):
    sent["rows"] = 5
    query = "start_time=2026-06-24T02:17:07%2B00:00&end=2026-06-25T00:00:00%2B00:00&method=GET&order_dir=asc&limit=5"
    next_url = (await _get(app, f"{LOGS_PATH}?{query}")).json()["next"]

    assert next_url.startswith(f"{LOGS_PATH}?")
    resp = await _get(app, next_url)
    assert resp.status_code == 200
    params = sent["params"]
    assert params["start_id"] == 5
    assert params["limit"] == 5
    assert params["start_time"] == 1782267427
    assert params["end"] == 1782345600
    assert params["method"] == "GET"
    assert params["order_dir"] == "asc"


async def test_next_replaces_rather_than_appends_cursor(app, sent):
    sent["rows"] = 2
    first = (await _get(app, f"{LOGS_PATH}?start_time=2026-06-24T02:17:07%2B00:00&limit=2")).json()[
        "next"
    ]
    second = (await _get(app, first)).json()["next"]

    assert second.count("start_id=") == 1
    assert (await _get(app, second)).json()["next"] != second


async def test_limit_is_bounded(app, sent):
    sent["rows"] = 0
    assert (
        await _get(app, f"{LOGS_PATH}?start_time=2026-06-24T02:17:07%2B00:00&limit=1001")
    ).status_code == 422
    assert (
        await _get(app, f"{LOGS_PATH}?start_time=2026-06-24T02:17:07%2B00:00&limit=0")
    ).status_code == 422
