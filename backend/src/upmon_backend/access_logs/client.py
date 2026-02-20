import httpx

from .ssh_session import SSHSession

_client = httpx.AsyncClient(timeout=30)


async def query_relay(
    session: SSHSession, sql: str, params: list | None = None
) -> dict:
    resp = await _client.post(
        session.base_url,
        json={"sql": sql, "params": params or []},
    )
    resp.raise_for_status()
    return resp.json()
