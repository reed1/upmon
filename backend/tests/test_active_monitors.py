import json

import pytest
from httpx import ASGITransport, AsyncClient

from upmon_backend import access, active_monitors
from upmon_backend.config import Settings
from upmon_backend.main import create_app


class FakePool:
    def __init__(self, rows):
        self._rows = rows

    async def fetch(self, *args, **kwargs):
        return self._rows


def _status_row(project_id, site_key):
    return {
        "project_id": project_id,
        "site_key": site_key,
        "url": f"https://{project_id}.example/health",
        "status_code": 200,
        "response_ms": 10,
        "is_up": True,
        "error_type": None,
        "error_message": None,
        "last_checked_at": "2026-07-16T12:00:00+00:00",
        "last_up_at": "2026-07-16T12:00:00+00:00",
    }


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "_cache", access._AccessCache())
    monkeypatch.setattr(active_monitors, "_cache", active_monitors._Cache())

    users = tmp_path / "users.yaml"
    users.write_text("users:\n  - email: admin@b.com\n    role: admin\n")

    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"projects": [{"id": "abubot", "monitors": [{"site_key": "prod"}]}]})
    )

    settings = Settings(
        database_url="postgres://fake:fake@localhost/fake",
        api_key="test-key",
        frontend_dir="/tmp",
        users_config=str(users),
        monitors_config=str(config),
    )
    application = create_app(settings)
    application.state.pool = FakePool(
        [_status_row("abubot", "prod"), _status_row("telebot-infaq", "prod")]
    )
    return application


async def _get(app, path, headers=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path, headers=headers or {})


async def test_status_hides_monitor_absent_from_config(app):
    resp = await _get(app, "/api/v1/status", {"remote-email": "admin@b.com"})
    assert resp.status_code == 200
    returned = {(r["project_id"], r["site_key"]) for r in resp.json()}
    assert ("abubot", "prod") in returned
    assert ("telebot-infaq", "prod") not in returned


async def test_status_shows_all_when_config_missing(app):
    # Fail-open: no monitors config -> no filtering, retained rows still shown.
    app.state.settings.monitors_config = "/nonexistent/config.json"
    resp = await _get(app, "/api/v1/status", {"remote-email": "admin@b.com"})
    assert resp.status_code == 200
    returned = {(r["project_id"], r["site_key"]) for r in resp.json()}
    assert ("telebot-infaq", "prod") in returned
