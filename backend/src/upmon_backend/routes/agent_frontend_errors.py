from fastapi import APIRouter, Depends, Query, Request

from ..access import User, get_current_user
from .agent_logs import (
    AgentConfig,
    _get_site,
    _next_url,
    _query_agent,
    _to_epoch,
    get_agent_config,
)

router = APIRouter(prefix="/frontend-errors")


@router.get("/sites/{project_id}/{site_key}/logs")
async def get_frontend_errors(
    request: Request,
    project_id: str,
    site_key: str,
    start_time: str = Query(),
    start_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    end: str | None = Query(None),
    kind: str | None = Query(None),
    os: str | None = Query(None),
    client_type: str | None = Query(None),
    fingerprint: str | None = Query(None),
    session_id: str | None = Query(None),
    order_by: str = Query("epoch_sec"),
    order_dir: str = Query("desc"),
    config: AgentConfig = Depends(get_agent_config),
    user: User = Depends(get_current_user),
) -> dict:
    user.ensure_access(project_id)
    site = _get_site(config, project_id, site_key)
    result = await _query_agent(
        site,
        "frontend_errors",
        {
            "start_time": _to_epoch(start_time),
            "start_id": start_id,
            "limit": limit,
            "end": _to_epoch(end) if end else None,
            "kind": kind,
            "os": os,
            "client_type": client_type,
            "fingerprint": fingerprint,
            "session_id": session_id,
            "order_by": order_by,
            "order_dir": order_dir,
        },
    )
    return {**result, "next": _next_url(request, result, limit)}


@router.get("/sites/{project_id}/{site_key}/stats")
async def get_frontend_error_stats(
    project_id: str,
    site_key: str,
    start_time: str = Query(),
    end: str | None = Query(None),
    kind: str | None = Query(None),
    os: str | None = Query(None),
    client_type: str | None = Query(None),
    fingerprint: str | None = Query(None),
    session_id: str | None = Query(None),
    config: AgentConfig = Depends(get_agent_config),
    user: User = Depends(get_current_user),
) -> dict:
    user.ensure_access(project_id)
    site = _get_site(config, project_id, site_key)
    result = await _query_agent(
        site,
        "frontend_error_stats",
        {
            "start_time": _to_epoch(start_time),
            "end": _to_epoch(end) if end else None,
            "kind": kind,
            "os": os,
            "client_type": client_type,
            "fingerprint": fingerprint,
            "session_id": session_id,
        },
    )
    return {
        "summary": result["summary"],
        **_split_distributions(result["distributions"]),
        "volume": result["volume"],
        "top_errors": result["top_errors"],
    }


_DISTRIBUTIONS = ("kind", "error_class", "os", "client_type")


def _split_distributions(result: dict) -> dict:
    groups: dict[str, list] = {name: [] for name in _DISTRIBUTIONS}
    for row in result["rows"]:
        if row[1] is not None:
            groups[row[0]].append(row[1:])

    for rows in groups.values():
        rows.sort(key=lambda r: r[1], reverse=True)

    return {
        f"{name}_distribution": {"columns": [name, "count"], "rows": groups[name]}
        for name in _DISTRIBUTIONS
    }
