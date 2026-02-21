import pytest
from httpx import ASGITransport, AsyncClient

from upmon_backend.config import Settings
from upmon_backend.main import create_app


@pytest.fixture
def app():
    settings = Settings(
        database_url="postgres://fake:fake@localhost/fake",
        api_key="test-key",
        frontend_dir="/tmp",
    )
    return create_app(settings)


async def test_missing_api_key_returns_401(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/status")
    assert resp.status_code == 401


async def test_wrong_api_key_returns_401(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/status", headers={"x-api-key": "wrong-key"})
    assert resp.status_code == 401
