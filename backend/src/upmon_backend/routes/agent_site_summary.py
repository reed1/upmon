from fastapi import APIRouter, Depends, Request

from ..auth import require_api_key

router = APIRouter(
    prefix="/api/v1/access-logs",
    dependencies=[Depends(require_api_key)],
)


@router.get("/sites/{project_id}/{site_key}/summary")
async def get_site_summary(
    request: Request,
    project_id: str,
    site_key: str,
) -> dict:
    pool = request.app.state.pool
    cleanup_rows, error_rows = await _fetch_summary(pool, project_id, site_key)
    return {
        "cleanup_logs": [dict(r) for r in cleanup_rows],
        "error_counts": [dict(r) for r in error_rows],
    }


async def _fetch_summary(pool, project_id: str, site_key: str):
    import asyncio

    return await asyncio.gather(
        pool.fetch(
            """SELECT id, executed_at, retention_days,
                      status_code, deleted_count, duration_ms, error_message
               FROM agent_daily_cleanup
               WHERE project_id = $1 AND site_key = $2
               ORDER BY id DESC
               LIMIT 5""",
            project_id,
            site_key,
        ),
        pool.fetch(
            """SELECT date, error_count
               FROM agent_daily_error_count
               WHERE project_id = $1 AND site_key = $2
                 AND success = TRUE
               ORDER BY date DESC
               LIMIT 5""",
            project_id,
            site_key,
        ),
    )
