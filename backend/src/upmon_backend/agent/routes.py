import asyncio
import json
import logging
from datetime import datetime as dt

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import require_api_key

logger = logging.getLogger("upmon_backend.agent")

_client = httpx.AsyncClient(timeout=30)

router = APIRouter(
    prefix="/api/v1/access-logs",
    dependencies=[Depends(require_api_key)],
)


def _time_conditions(start: str | None, end: str | None, minutes: int | None) -> tuple[list[str], list]:
    conditions: list[str] = []
    bindings: list = []
    if start is not None and end is not None:
        conditions.append("timestamp >= ?")
        bindings.append(start)
        conditions.append("timestamp <= ?")
        bindings.append(end)
    elif minutes is not None:
        conditions.append("timestamp >= datetime('now', ?)")
        bindings.append(f"-{minutes} minutes")
    return conditions, bindings


def _bucket_format(span_minutes: float) -> str:
    if span_minutes < 180:
        return "%Y-%m-%dT%H:%M:00"
    if span_minutes < 4320:
        return "%Y-%m-%dT%H:00:00"
    return "%Y-%m-%dT00:00:00"


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
    minutes: int | None = Query(None, ge=1),
    status_code: int | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
) -> dict:
    site = _get_site(request, project_id, site_key)

    conditions, bindings = _time_conditions(start, end, minutes)

    if status_code is not None:
        conditions.append("status_code = ?")
        bindings.append(status_code)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM access_logs {where} ORDER BY timestamp DESC LIMIT 100"

    return await _query_agent(site, sql, bindings)


@router.get("/sites/{project_id}/{site_key}/stats")
async def get_stats(
    request: Request,
    project_id: str,
    site_key: str,
    minutes: int | None = Query(None, ge=1),
    start: str | None = Query(None),
    end: str | None = Query(None),
) -> dict:
    site = _get_site(request, project_id, site_key)

    conditions, bindings = _time_conditions(start, end, minutes)
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

    if start is not None and end is not None:
        span = (dt.fromisoformat(end) - dt.fromisoformat(start)).total_seconds() / 60
    elif minutes is not None:
        span = float(minutes)
    else:
        span = float("inf")
    bucket_fmt = _bucket_format(span)

    volume_sql = f"""
        SELECT
            strftime('{bucket_fmt}', timestamp) AS bucket,
            SUM(CASE WHEN status_code BETWEEN 200 AND 299 THEN 1 ELSE 0 END) AS ok,
            SUM(CASE WHEN status_code < 200 OR status_code >= 300 THEN 1 ELSE 0 END) AS not_ok
        FROM access_logs {where}
        GROUP BY bucket
        ORDER BY bucket
    """

    summary, status_distribution, volume = await asyncio.gather(
        _query_agent(site, summary_sql, bindings),
        _query_agent(site, dist_sql, bindings),
        _query_agent(site, volume_sql, bindings),
    )

    return {"summary": summary, "status_distribution": status_distribution, "volume": volume}
