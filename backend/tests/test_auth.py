import pytest
from httpx import ASGITransport, AsyncClient

from upmon_backend import access
from upmon_backend.config import Settings
from upmon_backend.main import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "_cache", access._AccessCache())
    users = tmp_path / "users.yaml"
    users.write_text("users:\n  - email: admin@b.com\n    role: admin\n")
    settings = Settings(
        database_url="postgres://fake:fake@localhost/fake",
        api_key="test-key",
        frontend_dir="/tmp",
        users_config=str(users),
    )
    return create_app(settings)


async def _get(app, path, headers=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path, headers=headers or {})


async def test_api_requires_pangolin_identity(app):
    resp = await _get(app, "/api/v1/status")
    assert resp.status_code == 401


async def test_api_unknown_user_forbidden(app):
    resp = await _get(app, "/api/v1/status", {"remote-email": "stranger@b.com"})
    assert resp.status_code == 403


async def test_public_api_missing_key_returns_401(app):
    resp = await _get(app, "/api-public/v1/status")
    assert resp.status_code == 401


async def test_public_api_wrong_key_returns_401(app):
    resp = await _get(app, "/api-public/v1/status", {"x-api-key": "wrong-key"})
    assert resp.status_code == 401
