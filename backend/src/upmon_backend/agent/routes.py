import asyncio
import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import require_api_key

logger = logging.getLogger("upmon_backend.agent")

_client = httpx.AsyncClient(timeout=30)

router = APIRouter(
    prefix="/api/v1/access-logs",
    dependencies=[Depends(require_api_key)],
)


def _get_site(request: Request, project_id: str, site_key: str):
    config = request.app.state.agent_config
    for site in config.sites:
        if site.project_id == project_id and site.site_key == site_key:
            return site
    raise HTTPException(status_code=404, detail=f"Unknown site: {project_id}/{site_key}")


async def _query_agent(site, sql: str, bindings: list | None = None) -> dict:
    query_params = {
        "api_key": site.agent_api_key,
        "sql": sql,
        "bindings": json.dumps(bindings or []),
    }
    resp = await _client.get(site.agent_url, params=query_params)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Agent error: {resp.text}")
    data = resp.json()
    if data.get("error"):
        raise HTTPException(status_code=502, detail=f"Agent error: {data['error']}")
    return data["result"]


@router.get("/sites")
async def list_sites(request: Request) -> list[dict]:
    return [{"project_id": site.project_id, "site_key": site.site_key} for site in request.app.state.agent_config.sites]


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
    site = _get_site(request, project_id, site_key)

    conditions = []
    bindings: list = []

    if path is not None:
        conditions.append("path = ?")
        bindings.append(path)
    if method is not None:
        conditions.append("method = ?")
        bindings.append(method)
    if status_code is not None:
        conditions.append("status_code = ?")
        bindings.append(status_code)
    if min_duration_ms is not None:
        conditions.append("duration_ms >= ?")
        bindings.append(min_duration_ms)
    if has_exception is not None:
        if has_exception:
            conditions.append("exception_class IS NOT NULL")
        else:
            conditions.append("exception_class IS NULL")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM access_logs {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    bindings.extend([limit, offset])

    return await _query_agent(site, sql, bindings)


@router.get("/sites/{project_id}/{site_key}/stats")
async def get_stats(
    request: Request,
    project_id: str,
    site_key: str,
    path: str | None = Query(None),
) -> dict:
    site = _get_site(request, project_id, site_key)

    conditions = []
    bindings: list = []

    if path is not None:
        conditions.append("path = ?")
        bindings.append(path)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    summary_sql = f"""
        SELECT
            COUNT(*) AS total_requests,
            ROUND(AVG(duration_ms), 2) AS avg_duration_ms,
            ROUND(MIN(duration_ms), 2) AS min_duration_ms,
            ROUND(MAX(duration_ms), 2) AS max_duration_ms,
            SUM(CASE WHEN exception_class IS NOT NULL THEN 1 ELSE 0 END) AS total_exceptions
        FROM access_logs {where}
    """

    dist_sql = f"""
        SELECT status_code, COUNT(*) AS count
        FROM access_logs {where}
        GROUP BY status_code
        ORDER BY status_code
    """

    summary, status_distribution = await asyncio.gather(
        _query_agent(site, summary_sql, bindings),
        _query_agent(site, dist_sql, bindings),
    )

    return {"summary": summary, "status_distribution": status_distribution}
