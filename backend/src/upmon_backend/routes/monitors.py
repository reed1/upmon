import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request

from .. import db
from ..auth import require_api_key
from ..models import HourlySummary, MonitorStatus, SiteSummaryEntry

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_api_key)],
)


@router.get("/status", response_model=list[MonitorStatus])
async def status(
    request: Request,
    project_id: str | None = Query(None),
) -> list[dict]:
    rows = await db.get_monitor_statuses(request.app.state.pool, project_id)
    return [dict(r) for r in rows]


@router.get("/daily-summary", response_model=HourlySummary)
async def daily_summary(
    request: Request,
    project_id: str | None = Query(None),
    days: int = Query(7),
) -> HourlySummary:
    days = max(1, min(days, 90))
    pool = request.app.state.pool

    summary, cleanup_rows, error_rows = await asyncio.gather(
        db.get_hourly_summary(pool, project_id, days),
        pool.fetch(
            """SELECT DISTINCT ON (project_id, site_key)
                      project_id, site_key, executed_at, error_message
               FROM agent_daily_cleanup
               ORDER BY project_id, site_key, id DESC"""
        ),
        pool.fetch(
            """SELECT DISTINCT ON (project_id, site_key)
                      project_id, site_key, date, error_count
               FROM agent_daily_error_count
               WHERE success = TRUE
               ORDER BY project_id, site_key, date DESC"""
        ),
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=2)

    for r in cleanup_rows:
        entry = summary.setdefault(r["project_id"], {}).setdefault(r["site_key"], SiteSummaryEntry(days=[]))
        entry.cleanup_ok = r["error_message"] is None and r["executed_at"] >= cutoff

    for r in error_rows:
        entry = summary.setdefault(r["project_id"], {}).setdefault(r["site_key"], SiteSummaryEntry(days=[]))
        entry.errors_ok = r["error_count"] == 0

    return summary
