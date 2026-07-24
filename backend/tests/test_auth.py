import pytest
from httpx import ASGITransport, AsyncClient

from upmon_backend import access
from upmon_backend.access import derive_api_key
from upmon_backend.config import Settings
from upmon_backend.main import create_app

SECRET = "test-secret"
ADMIN_EMAIL = "admin@b.com"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "_cache", access._AccessCache())
    users = tmp_path / "users.yaml"
    users.write_text(f"users:\n  - email: {ADMIN_EMAIL}\n    role: admin\n")
    settings = Settings(
        database_url="postgres://fake:fake@localhost/fake",
        api_key_secret=SECRET,
        frontend_dir="/tmp",
        users_config=str(users),
        dev_identity_email=None,
    )
    return create_app(settings)


async def _get(app, path, headers=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path, headers=headers or {})


async def test_api_requires_api_key(app):
    resp = await _get(app, "/api/v1/status")
    assert resp.status_code == 401


async def test_api_rejects_wrong_key(app):
    resp = await _get(app, "/api/v1/status", {"authorization": "Bearer wrong-key"})
    assert resp.status_code == 401


async def test_api_key_issuer_requires_identity(app):
    resp = await _get(app, "/pangolin/api-key")
    assert resp.status_code == 401


async def test_api_key_issuer_rejects_unknown_email(app):
    resp = await _get(app, "/pangolin/api-key", {"remote-email": "stranger@b.com"})
    assert resp.status_code == 403


async def test_api_key_issuer_returns_derivable_key(app):
    resp = await _get(app, "/pangolin/api-key", {"remote-email": ADMIN_EMAIL})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == ADMIN_EMAIL
    assert body["api_key"] == derive_api_key(SECRET, ADMIN_EMAIL)
    assert body["api_key"] in access._cache.by_key
