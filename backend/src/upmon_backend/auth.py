from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def require_api_key(
    request: Request,
    key: str | None = Security(_api_key_header),
) -> None:
    if not key or key != request.app.state.settings.api_key:
        raise HTTPException(status_code=401)
