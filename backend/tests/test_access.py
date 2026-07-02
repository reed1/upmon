import os

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from upmon_backend import access
from upmon_backend.access import AccessConfig, User, resolve_user


def _users(raw: dict) -> dict:
    config = AccessConfig.model_validate(raw)
    return {u.email.strip().lower(): u for u in config.users}


def test_viewer_requires_project_ids():
    with pytest.raises(ValidationError):
        AccessConfig.model_validate({"users": [{"email": "a@b.com", "role": "viewer"}]})


def test_unknown_role_rejected():
    with pytest.raises(ValidationError):
        AccessConfig.model_validate({"users": [{"email": "a@b.com", "role": "owner"}]})


def test_admin_sees_every_project():
    users = _users({"users": [{"email": "admin@b.com", "role": "admin"}]})
    user = resolve_user(users, "admin@b.com")
    assert user.project_ids is None
    assert user.can_access("anything")


def test_viewer_scoped_to_project_ids():
    users = _users({"users": [{"email": "v@b.com", "role": "viewer", "project_ids": ["p1", "p2"]}]})
    user = resolve_user(users, "V@B.com")  # case-insensitive match
    assert user.can_access("p1")
    assert not user.can_access("p3")
    user.ensure_access("p2")
    with pytest.raises(HTTPException) as exc:
        user.ensure_access("p3")
    assert exc.value.status_code == 403


def test_viewer_denied_admin_actions():
    users = _users({"users": [{"email": "v@b.com", "role": "viewer", "project_ids": ["p1"]}]})
    user = resolve_user(users, "v@b.com")
    with pytest.raises(HTTPException) as exc:
        user.ensure_admin()
    assert exc.value.status_code == 403


def test_missing_identity_is_401():
    users = _users({"users": [{"email": "a@b.com", "role": "admin"}]})
    with pytest.raises(HTTPException) as exc:
        resolve_user(users, None)
    assert exc.value.status_code == 401


def test_unknown_user_is_403():
    users = _users({"users": [{"email": "a@b.com", "role": "admin"}]})
    with pytest.raises(HTTPException) as exc:
        resolve_user(users, "stranger@b.com")
    assert exc.value.status_code == 403


def test_disabled_when_config_absent():
    user = resolve_user(None, None)
    assert user == User(email="*", role="admin", project_ids=None)


def test_load_parses_and_reloads_on_change(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "_cache", access._AccessCache())
    path = tmp_path / "users.yaml"
    path.write_text("users:\n  - email: a@b.com\n    role: admin\n")
    loaded = access._load(str(path))
    assert set(loaded) == {"a@b.com"}

    original_mtime = path.stat().st_mtime
    path.write_text(
        "users:\n  - email: a@b.com\n    role: viewer\n    project_ids: [p1]\n"
        "  - email: c@d.com\n    role: admin\n"
    )
    os.utime(path, (original_mtime + 10, original_mtime + 10))
    reloaded = access._load(str(path))
    assert set(reloaded) == {"a@b.com", "c@d.com"}


def test_load_missing_file_disables(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "_cache", access._AccessCache())
    assert access._load(str(tmp_path / "nope.yaml")) is None
