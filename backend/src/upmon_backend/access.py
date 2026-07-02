import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from fastapi import HTTPException, Request
from pydantic import BaseModel, model_validator

logger = logging.getLogger("upmon_backend.access")

IDENTITY_HEADER = "remote-email"


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
            raise HTTPException(status_code=403, detail=f"Not authorized for project '{project_id}'")

    def ensure_admin(self) -> None:
        if self.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")


@dataclass
class _AccessCache:
    users: dict[str, UserAccess] | None = None
    mtime: float | None = None
    missing_logged: bool = False


_cache = _AccessCache()


def _load(path: str) -> dict[str, UserAccess] | None:
    file = Path(path)
    if not file.exists():
        if not _cache.missing_logged:
            logger.warning("Access config %s not found; access control DISABLED (all users treated as admin)", path)
            _cache.missing_logged = True
        _cache.users = None
        _cache.mtime = None
        return None

    _cache.missing_logged = False
    mtime = file.stat().st_mtime
    if _cache.users is not None and mtime == _cache.mtime:
        return _cache.users

    with open(file) as f:
        config = AccessConfig.model_validate(yaml.safe_load(f) or {})
    _cache.users = {u.email.strip().lower(): u for u in config.users}
    _cache.mtime = mtime
    logger.info("Loaded access config from %s (%d users)", path, len(_cache.users))
    return _cache.users


def resolve_user(users: dict[str, UserAccess] | None, email_header: str | None) -> User:
    if users is None:
        return User(email="*", role="admin", project_ids=None)

    email = (email_header or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail=f"Missing {IDENTITY_HEADER} header")

    entry = users.get(email)
    if entry is None:
        raise HTTPException(status_code=403, detail=f"User not authorized: {email}")

    project_ids = None if entry.role == "admin" else frozenset(entry.project_ids)
    return User(email=email, role=entry.role, project_ids=project_ids)


def get_current_user(request: Request) -> User:
    users = _load(request.app.state.settings.users_config)
    return resolve_user(users, request.headers.get(IDENTITY_HEADER))
