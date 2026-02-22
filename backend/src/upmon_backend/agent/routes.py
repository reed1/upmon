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


async def _query_agent(site, query: str, params: dict | None = None) -> dict:
    query_params = {"query": query, "api_key": site.agent_api_key}
    if params:
        query_params.update(params)
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
    params = {"limit": str(limit), "offset": str(offset)}
    if path is not None:
        params["path"] = path
    if method is not None:
        params["method"] = method
    if status_code is not None:
        params["status_code"] = str(status_code)
    if min_duration_ms is not None:
        params["min_duration_ms"] = str(min_duration_ms)
    if has_exception is not None:
        params["has_exception"] = str(has_exception).lower()
    return await _query_agent(site, "logs", params)


@router.get("/sites/{project_id}/{site_key}/stats")
async def get_stats(
    request: Request,
    project_id: str,
    site_key: str,
    path: str | None = Query(None),
) -> dict:
    site = _get_site(request, project_id, site_key)
    params = {}
    if path is not None:
        params["path"] = path
    return await _query_agent(site, "stats", params)
