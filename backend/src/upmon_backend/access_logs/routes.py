import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import require_api_key
from .client import query_relay

logger = logging.getLogger("upmon_backend.access_logs")

router = APIRouter(
    prefix="/api/v1/access-logs",
    dependencies=[Depends(require_api_key)],
)


def _get_site(request: Request, project_id: str, site_key: str):
    config = request.app.state.access_logs_config
    for site in config.sites:
        if site.project_id == project_id and site.site_key == site_key:
            return site
    raise HTTPException(status_code=404, detail=f"Unknown site: {project_id}/{site_key}")


async def _get_session(request: Request, project_id: str, site_key: str):
    site = _get_site(request, project_id, site_key)
    session_key = f"{project_id}/{site_key}"
    manager = request.app.state.ssh_session_manager
    try:
        return await manager.get_session(session_key, site.ssh_host, site.db_path)
    except RuntimeError as e:
        logger.error("Failed to start relay for %s: %s", session_key, e)
        raise HTTPException(status_code=500, detail=str(e))


async def _query(request: Request, project_id: str, site_key: str, sql: str, params: list):
    session = await _get_session(request, project_id, site_key)
    session_key = f"{project_id}/{site_key}"
    manager = request.app.state.ssh_session_manager
    try:
        return await query_relay(session, sql, params)
    except httpx.ConnectError:
        manager.clear_session(session_key)
        raise HTTPException(status_code=502, detail="SSH relay connection lost")


@router.get("/sites")
async def list_sites(request: Request) -> list[dict]:
    return [
        {"project_id": site.project_id, "site_key": site.site_key}
        for site in request.app.state.access_logs_config.sites
    ]


@router.get("/sites/{project_id}/{site_key}/logs")
async def get_logs(
    request: Request,
    project_id: str,
    site_key: str,
    path: str | None = Query(None),
    method: str | None = Query(None),
    status_code: int | None = Query(None),
    min_duration_ms: float | None = Query(None),
    has_exception: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    conditions = []
    params = []

    if path is not None:
        conditions.append("path LIKE ?")
        params.append(f"%{path}%")
    if method is not None:
        conditions.append("method = ?")
        params.append(method.upper())
    if status_code is not None:
        conditions.append("status_code = ?")
        params.append(status_code)
    if min_duration_ms is not None:
        conditions.append("duration_ms >= ?")
        params.append(min_duration_ms)
    if has_exception is True:
        conditions.append("exception IS NOT NULL")
    elif has_exception is False:
        conditions.append("exception IS NULL")

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM access_logs{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    return await _query(request, project_id, site_key, sql, params)


@router.get("/sites/{project_id}/{site_key}/stats")
async def get_stats(
    request: Request,
    project_id: str,
    site_key: str,
    path: str | None = Query(None),
) -> dict:
    conditions = []
    params = []

    if path is not None:
        conditions.append("path LIKE ?")
        params.append(f"%{path}%")

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

    sql = f"""
        SELECT
            COUNT(*) as total_requests,
            AVG(duration_ms) as avg_duration_ms,
            MIN(duration_ms) as min_duration_ms,
            MAX(duration_ms) as max_duration_ms
        FROM access_logs{where}
    """
    summary = await _query(request, project_id, site_key, sql, params)

    status_sql = f"""
        SELECT status_code, COUNT(*) as count
        FROM access_logs{where}
        GROUP BY status_code
        ORDER BY count DESC
    """
    status_dist = await _query(request, project_id, site_key, status_sql, list(params))

    return {
        "summary": summary,
        "status_distribution": status_dist,
    }
