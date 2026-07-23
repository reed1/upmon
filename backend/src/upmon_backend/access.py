import hashlib
import hmac
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from fastapi import HTTPException, Request
from pydantic import BaseModel, model_validator

logger = logging.getLogger("upmon_backend.access")

IDENTITY_HEADER = "remote-email"


def derive_api_key(secret: str, email: str) -> str:
    normalized = email.strip().lower().encode()
    return hmac.new(secret.encode(), normalized, hashlib.sha256).hexdigest()


class UserAccess(BaseModel):
    email: str
    role: Literal["admin", "viewer"]
    project_ids: list[str] = []

    @model_validator(mode="after")
    def _require_scope_for_viewer(self) -> "UserAccess":
        if self.role == "viewer" and not self.project_ids:
            raise ValueError(f"viewer '{self.email}' requires a non-empty project_ids list")
        return self


class AccessConfig(BaseModel):
    users: list[UserAccess]


@dataclass(frozen=True)
class User:
    email: str
    role: str
    project_ids: frozenset[str] | None  # None => every project (admin)

    def can_access(self, project_id: str) -> bool:
        return self.project_ids is None or project_id in self.project_ids

    def ensure_access(self, project_id: str) -> None:
        if not self.can_access(project_id):
            raise HTTPException(
                status_code=403, detail=f"Not authorized for project '{project_id}'"
            )

    def ensure_admin(self) -> None:
        if self.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")


def _to_user(email: str, entry: UserAccess) -> User:
    project_ids = None if entry.role == "admin" else frozenset(entry.project_ids)
    return User(email=email, role=entry.role, project_ids=project_ids)


@dataclass
class _AccessCache:
    by_email: dict[str, UserAccess] | None = None
    by_key: dict[str, User] | None = None
    mtime: float | None = None
    missing_logged: bool = False


_cache = _AccessCache()


def _load(path: str, secret: str) -> dict[str, UserAccess] | None:
    file = Path(path)
    if not file.exists():
        if not _cache.missing_logged:
            logger.warning("Access config %s not found; no API keys are valid", path)
            _cache.missing_logged = True
        _cache.by_email = None
        _cache.by_key = None
        _cache.mtime = None
        return None

    _cache.missing_logged = False
    mtime = file.stat().st_mtime
    if _cache.by_email is not None and mtime == _cache.mtime:
        return _cache.by_email

    with open(file) as f:
        config = AccessConfig.model_validate(yaml.safe_load(f) or {})
    by_email = {u.email.strip().lower(): u for u in config.users}
    _cache.by_email = by_email
    _cache.by_key = {
        derive_api_key(secret, email): _to_user(email, entry) for email, entry in by_email.items()
    }
    _cache.mtime = mtime
    logger.info("Loaded access config from %s (%d users)", path, len(by_email))
    return by_email


def resolve_user(users: dict[str, UserAccess] | None, email_header: str | None) -> User:
    if users is None:
        return User(email="*", role="admin", project_ids=None)

    email = (email_header or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail=f"Missing {IDENTITY_HEADER} header")

    entry = users.get(email)
    if entry is None:
        raise HTTPException(status_code=403, detail=f"User not authorized: {email}")

    return _to_user(email, entry)


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def require_api_key(request: Request) -> None:
    """Identity for the API-key-gated /api mount: the Bearer token maps to a users.yaml identity."""
    settings = request.app.state.settings
    _load(settings.users_config, settings.api_key_secret)
    token = _bearer_token(request)
    user = _cache.by_key.get(token) if (_cache.by_key is not None and token) else None
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    request.state.user = user


def require_pangolin_user(request: Request) -> User:
    """Identity for the SSO-protected /pangolin key issuer: resolved from the Pangolin header."""
    settings = request.app.state.settings
    users = _load(settings.users_config, settings.api_key_secret)
    user = resolve_user(users, request.headers.get(IDENTITY_HEADER))
    request.state.user = user
    return user


def get_current_user(request: Request) -> User:
    return request.state.user
