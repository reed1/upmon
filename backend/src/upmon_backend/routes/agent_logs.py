import asyncio
import json
import logging
from functools import lru_cache
from datetime import datetime as dt, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from ..auth import require_api_key

logger = logging.getLogger("upmon_backend.agent")

_client = httpx.AsyncClient(timeout=30)


class AgentSite(BaseModel):
    project_id: str
    site_key: str
    agent_url: str
    agent_api_key: str


class AgentConfig(BaseModel):
    sites: list[AgentSite]


@lru_cache(maxsize=1)
def _load_agent_config(path: str) -> AgentConfig:
    with open(path) as f:
        return AgentConfig.model_validate(json.load(f))


def get_agent_config(request: Request) -> AgentConfig:
    path = request.app.state.settings.agent_config
    if not Path(path).exists():
        raise HTTPException(status_code=501, detail="Agent feature not configured")
    return _load_agent_config(path)


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


def _get_site(config: AgentConfig, project_id: str, site_key: str):
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
async def list_sites(config: AgentConfig = Depends(get_agent_config)) -> list[dict]:
    return [{"project_id": site.project_id, "site_key": site.site_key} for site in config.sites]


_LOGS_ORDER_COLUMNS = {"epoch_sec", "method", "path", "status_code", "duration_ms"}


@router.get("/sites/{project_id}/{site_key}/logs")
async def get_logs(
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
    config: AgentConfig = Depends(get_agent_config),
) -> dict:
    site = _get_site(config, project_id, site_key)

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
    project_id: str,
    site_key: str,
    start: str = Query(),
    end: str | None = Query(None),
    exception_type: str | None = Query(None),
    platform: str | None = Query(None),
    client_type: str | None = Query(None),
    method: str | None = Query(None),
    config: AgentConfig = Depends(get_agent_config),
) -> dict:
    site = _get_site(config, project_id, site_key)

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

    distributions_sql = f"""
        WITH base AS (
            SELECT * FROM access_log {time_where}
        )
        SELECT 'exception_type' AS dist,
            CASE
                WHEN exception_is_unexpected IS NULL THEN 'none'
                WHEN exception_is_unexpected = 0 THEN 'expected'
                ELSE 'unexpected'
            END AS value,
            COUNT(*) AS count
        FROM base
        GROUP BY value

        UNION ALL
        SELECT 'method', method, COUNT(*)
        FROM base
        GROUP BY method

        UNION ALL
        SELECT 'platform', platform, COUNT(*)
        FROM base
        GROUP BY platform

        UNION ALL
        SELECT 'client_type', client_type, COUNT(*)
        FROM base
        GROUP BY client_type
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

    summary, distributions, volume = await asyncio.gather(
        _query_agent(site, summary_sql, filtered_bindings),
        _query_agent(site, distributions_sql, time_bindings),
        _query_agent(site, volume_sql, filtered_bindings),
    )

    (
        exception_distribution,
        method_distribution,
        platform_distribution,
        client_type_distribution,
    ) = _split_distributions(distributions)

    return {
        "summary": summary,
        "exception_distribution": exception_distribution,
        "method_distribution": method_distribution,
        "platform_distribution": platform_distribution,
        "client_type_distribution": client_type_distribution,
        "volume": volume,
    }


def _split_distributions(result: dict) -> tuple[dict, dict, dict, dict]:
    groups: dict[str, list] = {
        "exception_type": [],
        "method": [],
        "platform": [],
        "client_type": [],
    }
    for row in result["rows"]:
        if row[1] is not None:
            groups[row[0]].append(row[1:])

    groups["exception_type"].sort(key=lambda r: r[0])
    for key in ("method", "platform", "client_type"):
        groups[key].sort(key=lambda r: r[1], reverse=True)

    column_names = {
        "exception_type": ["exception_type", "count"],
        "method": ["method", "count"],
        "platform": ["platform", "count"],
        "client_type": ["client_type", "count"],
    }
    return tuple(
        {"columns": column_names[k], "rows": groups[k]} for k in ("exception_type", "method", "platform", "client_type")
    )
