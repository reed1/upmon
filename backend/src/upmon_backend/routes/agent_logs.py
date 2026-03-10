import json
import logging
import os
from base64 import b64encode
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime as dt
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from ..auth import require_api_key

logger = logging.getLogger("upmon_backend.agent")

_client = httpx.AsyncClient(timeout=30)
_client_no_verify = httpx.AsyncClient(timeout=30, verify=False)


class AgentSite(BaseModel):
    project_id: str
    site_key: str
    agent_url: str
    agent_api_key: str
    retention_days: int = 360
    tls_skip_verify: bool = False


class AgentConfig(BaseModel):
    sites: list[AgentSite]


@dataclass
class _AgentConfigCache:
    config: AgentConfig | None = None
    link_mtime: float | None = None
    real_mtime: float | None = None


_cache = _AgentConfigCache()


def _load_agent_config(path: str) -> AgentConfig:
    link_mtime = os.lstat(path).st_mtime
    real_mtime = Path(path).stat().st_mtime

    if _cache.config is not None and link_mtime == _cache.link_mtime and real_mtime == _cache.real_mtime:
        return _cache.config

    with open(path) as f:
        _cache.config = AgentConfig.model_validate(json.load(f))
    _cache.link_mtime = link_mtime
    _cache.real_mtime = real_mtime
    logger.info("Reloaded agent config from %s", path)
    return _cache.config


def get_agent_config(request: Request) -> AgentConfig:
    path = request.app.state.settings.agent_config
    if not Path(path).exists():
        raise HTTPException(status_code=501, detail="Agent feature not configured")
    return _load_agent_config(path)


router = APIRouter(
    prefix="/api/v1/access-logs",
    dependencies=[Depends(require_api_key)],
)


def _get_site(config: AgentConfig, project_id: str, site_key: str):
    for site in config.sites:
        if site.project_id == project_id and site.site_key == site_key:
            return site
    raise HTTPException(status_code=404, detail=f"Unknown site: {project_id}/{site_key}")


def _to_epoch(iso: str) -> int:
    return int(dt.fromisoformat(iso).timestamp())


async def _query_agent(site, view: str, params: dict) -> dict:
    payload = json.dumps(
        {
            "command": "query",
            "api_key": site.agent_api_key,
            "view": view,
            **params,
        }
    )
    query_params = {"q": b64encode(payload.encode()).decode()}
    client = _client_no_verify if site.tls_skip_verify else _client
    req = client.build_request("GET", site.agent_url, params=query_params)
    resp = await client.send(req)
    url = str(req.url)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Agent error: {resp.text}\nURL: {url}")
    data = resp.json()
    if data.get("error"):
        raise HTTPException(status_code=502, detail=f"Agent error: {data['error']}\nURL: {url}")
    return data["result"]


_JSON_PARSE_COLUMNS = {"query", "body", "files", "exception_traceback"}


def _parse_json_columns(result: dict, columns: Iterable[str] = _JSON_PARSE_COLUMNS) -> dict:
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


@router.get("/sites/{project_id}/{site_key}/logs")
async def get_logs(
    project_id: str,
    site_key: str,
    start: str = Query(),
    end: str | None = Query(None),
    exception_type: str | None = Query(None),
    os: str | None = Query(None),
    client_type: str | None = Query(None),
    method: str | None = Query(None),
    order_by: str = Query("epoch_sec"),
    order_dir: str = Query("desc"),
    config: AgentConfig = Depends(get_agent_config),
) -> dict:
    site = _get_site(config, project_id, site_key)
    result = await _query_agent(
        site,
        "logs",
        {
            "start": _to_epoch(start),
            "end": _to_epoch(end) if end else None,
            "exception_type": exception_type,
            "os": os,
            "client_type": client_type,
            "method": method,
            "order_by": order_by,
            "order_dir": order_dir,
        },
    )
    return _parse_json_columns(result)


@router.get("/sites/{project_id}/{site_key}/stats")
async def get_stats(
    project_id: str,
    site_key: str,
    start: str = Query(),
    end: str | None = Query(None),
    exception_type: str | None = Query(None),
    os: str | None = Query(None),
    client_type: str | None = Query(None),
    method: str | None = Query(None),
    config: AgentConfig = Depends(get_agent_config),
) -> dict:
    site = _get_site(config, project_id, site_key)
    result = await _query_agent(
        site,
        "stats",
        {
            "start": _to_epoch(start),
            "end": _to_epoch(end) if end else None,
            "exception_type": exception_type,
            "os": os,
            "client_type": client_type,
            "method": method,
        },
    )

    (
        exception_distribution,
        method_distribution,
        os_distribution,
        client_type_distribution,
    ) = _split_distributions(result["distributions"])

    return {
        "summary": result["summary"],
        "exception_distribution": exception_distribution,
        "method_distribution": method_distribution,
        "os_distribution": os_distribution,
        "client_type_distribution": client_type_distribution,
        "volume": result["volume"],
    }


def _split_distributions(result: dict) -> tuple[dict, dict, dict, dict]:
    groups: dict[str, list] = {
        "exception_type": [],
        "method": [],
        "os": [],
        "client_type": [],
    }
    for row in result["rows"]:
        if row[1] is not None:
            groups[row[0]].append(row[1:])

    groups["exception_type"].sort(key=lambda r: r[0])
    for key in ("method", "os", "client_type"):
        groups[key].sort(key=lambda r: r[1], reverse=True)

    column_names = {
        "exception_type": ["exception_type", "count"],
        "method": ["method", "count"],
        "os": ["os", "count"],
        "client_type": ["client_type", "count"],
    }
    return tuple(
        {"columns": column_names[k], "rows": groups[k]} for k in ("exception_type", "method", "os", "client_type")
    )
