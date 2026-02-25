import asyncio
import json
import logging
from datetime import datetime as dt, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import require_api_key

logger = logging.getLogger("upmon_backend.agent")

_client = httpx.AsyncClient(timeout=30)

router = APIRouter(
    prefix="/api/v1/access-logs",
    dependencies=[Depends(require_api_key)],
)


def _time_conditions(start: str, end: str | None) -> tuple[list[str], list]:
    conditions = ["epoch_sec >= ?"]
    bindings: list = [int(dt.fromisoformat(start).timestamp())]
    if end is not None:
        conditions.append("epoch_sec <= ?")
        bindings.append(int(dt.fromisoformat(end).timestamp()))
    return conditions, bindings


def _span_minutes(start: str, end: str | None) -> float:
    start_dt = dt.fromisoformat(start)
    end_dt = dt.fromisoformat(end) if end is not None else dt.now(timezone.utc)
    return (end_dt - start_dt).total_seconds() / 60


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


_JSON_PARSE_COLUMNS = ("query", "body", "files", "exception_traceback")


def _parse_json_columns(result: dict, columns: tuple[str, ...] = _JSON_PARSE_COLUMNS) -> dict:
    col_indices = {i for i, c in enumerate(result["columns"]) if c in columns}
    if not col_indices:
        return result

    def _parse_cell(i, v):
        if i in col_indices and isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                pass
        return v

    return {
        **result,
        "rows": [[_parse_cell(i, v) for i, v in enumerate(row)] for row in result["rows"]],
    }


@router.get("/sites")
async def list_sites(request: Request) -> list[dict]:
    return [{"project_id": site.project_id, "site_key": site.site_key} for site in request.app.state.agent_config.sites]


_LOGS_ORDER_COLUMNS = {"epoch_sec", "method", "path", "status_code", "duration_ms"}


@router.get("/sites/{project_id}/{site_key}/logs")
async def get_logs(
    request: Request,
    project_id: str,
    site_key: str,
    start: str = Query(),
    end: str | None = Query(None),
    exception_type: str | None = Query(None),
    platform: str | None = Query(None),
    client_type: str | None = Query(None),
    method: str | None = Query(None),
    order_by: str = Query("epoch_sec"),
    order_dir: str = Query("desc"),
) -> dict:
    site = _get_site(request, project_id, site_key)

    conditions, bindings = _time_conditions(start, end)

    if exception_type == "none":
        conditions.append("exception_is_unexpected IS NULL")
    elif exception_type == "expected":
        conditions.append("exception_is_unexpected = 0")
    elif exception_type == "unexpected":
        conditions.append("exception_is_unexpected = 1")
    if platform is not None:
        conditions.append("platform = ?")
        bindings.append(platform)
    if client_type is not None:
        conditions.append("client_type = ?")
        bindings.append(client_type)
    if method is not None:
        conditions.append("method = ?")
        bindings.append(method)

    if order_by not in _LOGS_ORDER_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Invalid order_by: {order_by}")
    direction = "ASC" if order_dir == "asc" else "DESC"

    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM access_log {where} ORDER BY {order_by} {direction} LIMIT 100"

    result = await _query_agent(site, sql, bindings)
    return _parse_json_columns(result)


@router.get("/sites/{project_id}/{site_key}/stats")
async def get_stats(
    request: Request,
    project_id: str,
    site_key: str,
    start: str = Query(),
    end: str | None = Query(None),
    exception_type: str | None = Query(None),
    platform: str | None = Query(None),
    client_type: str | None = Query(None),
    method: str | None = Query(None),
) -> dict:
    site = _get_site(request, project_id, site_key)

    time_conditions, time_bindings = _time_conditions(start, end)
    time_where = f"WHERE {' AND '.join(time_conditions)}"

    filtered_conditions = list(time_conditions)
    filtered_bindings = list(time_bindings)
    if exception_type == "none":
        filtered_conditions.append("exception_is_unexpected IS NULL")
    elif exception_type == "expected":
        filtered_conditions.append("exception_is_unexpected = 0")
    elif exception_type == "unexpected":
        filtered_conditions.append("exception_is_unexpected = 1")
    if platform is not None:
        filtered_conditions.append("platform = ?")
        filtered_bindings.append(platform)
    if client_type is not None:
        filtered_conditions.append("client_type = ?")
        filtered_bindings.append(client_type)
    if method is not None:
        filtered_conditions.append("method = ?")
        filtered_bindings.append(method)
    filtered_where = f"WHERE {' AND '.join(filtered_conditions)}"

    summary_sql = f"""
        SELECT
            COUNT(*) AS total_requests,
            ROUND(AVG(duration_ms), 2) AS avg_duration_ms,
            ROUND(MIN(duration_ms), 2) AS min_duration_ms,
            ROUND(MAX(duration_ms), 2) AS max_duration_ms,
            SUM(CASE WHEN exception_class IS NOT NULL THEN 1 ELSE 0 END) AS total_exceptions
        FROM access_log {filtered_where}
    """

    exception_dist_sql = f"""
        SELECT
            CASE
                WHEN exception_is_unexpected IS NULL THEN 'none'
                WHEN exception_is_unexpected = 0 THEN 'expected'
                ELSE 'unexpected'
            END AS exception_type,
            COUNT(*) AS count
        FROM access_log {time_where}
        GROUP BY exception_type
        ORDER BY exception_type
    """

    method_dist_sql = f"""
        SELECT method, COUNT(*) AS count
        FROM access_log {time_where}
        GROUP BY method
        ORDER BY count DESC
    """

    platform_dist_sql = f"""
        SELECT platform, COUNT(*) AS count
        FROM access_log {time_where} AND platform IS NOT NULL
        GROUP BY platform
        ORDER BY count DESC
    """

    client_type_dist_sql = f"""
        SELECT client_type, COUNT(*) AS count
        FROM access_log {time_where} AND client_type IS NOT NULL
        GROUP BY client_type
        ORDER BY count DESC
    """

    bucket_fmt = _bucket_format(_span_minutes(start, end))

    volume_sql = f"""
        SELECT
            strftime('{bucket_fmt}', epoch_sec, 'unixepoch') AS bucket,
            SUM(CASE WHEN status_code BETWEEN 200 AND 299 THEN 1 ELSE 0 END) AS ok,
            SUM(CASE WHEN status_code < 200 OR status_code >= 300 THEN 1 ELSE 0 END) AS not_ok
        FROM access_log {filtered_where}
        GROUP BY bucket
        ORDER BY bucket
    """

    (
        summary,
        exception_distribution,
        method_distribution,
        platform_distribution,
        client_type_distribution,
        volume,
    ) = await asyncio.gather(
        _query_agent(site, summary_sql, filtered_bindings),
        _query_agent(site, exception_dist_sql, time_bindings),
        _query_agent(site, method_dist_sql, time_bindings),
        _query_agent(site, platform_dist_sql, time_bindings),
        _query_agent(site, client_type_dist_sql, time_bindings),
        _query_agent(site, volume_sql, filtered_bindings),
    )

    return {
        "summary": summary,
        "exception_distribution": exception_distribution,
        "method_distribution": method_distribution,
        "platform_distribution": platform_distribution,
        "client_type_distribution": client_type_distribution,
        "volume": volume,
    }
