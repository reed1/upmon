from fastapi import APIRouter, Depends, Request

from ..access import User, derive_api_key, require_pangolin_user

router = APIRouter(prefix="/pangolin", include_in_schema=False)


@router.get("/api-key")
async def get_api_key(request: Request, user: User = Depends(require_pangolin_user)) -> dict:
    secret = request.app.state.settings.api_key_secret
    return {"email": user.email, "api_key": derive_api_key(secret, user.email)}
