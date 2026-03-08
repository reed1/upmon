import logging

from fastapi import APIRouter, Depends, Query, Request

from ..auth import require_api_key

logger = logging.getLogger("upmon_backend.agent_cleanup")

router = APIRouter(
    prefix="/api/v1/access-logs",
    dependencies=[Depends(require_api_key)],
)


@router.get("/cleanup-logs")
async def get_cleanup_logs(
    request: Request,
    project_id: str | None = Query(None),
    site_key: str | None = Query(None),
    days: int = Query(7, ge=1, le=365),
) -> list[dict]:
    pool = request.app.state.pool
    rows = await pool.fetch(
        """SELECT id, executed_at, project_id, site_key, agent_url,
                  retention_days, status_code, deleted_count, duration_ms, error
           FROM agent_cleanup_log
           WHERE executed_at > NOW() - make_interval(days => $1)
             AND ($2::text IS NULL OR project_id = $2)
             AND ($3::text IS NULL OR site_key = $3)
           ORDER BY executed_at DESC""",
        days,
        project_id,
        site_key,
    )
    return [dict(r) for r in rows]


@router.post("/cleanup/run")
async def trigger_cleanup(request: Request) -> dict:
    from ..scheduler import run_cleanup

    pool = request.app.state.pool
    agent_config_path = request.app.state.settings.agent_config
    await run_cleanup(pool, agent_config_path)
    return {"status": "ok"}
