import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request

from .. import db
from ..access import User, get_current_user
from ..auth import require_api_key
from ..models import HourlySummary, MonitorStatus, SiteSummaryEntry
from .agent_logs import _load_agent_config

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_api_key)],
)


@router.get("/status", response_model=list[MonitorStatus])
async def status(
    request: Request,
    project_id: str | None = Query(None),
    user: User = Depends(get_current_user),
) -> list[dict]:
    if project_id is not None:
        user.ensure_access(project_id)
    rows = await db.get_monitor_statuses(request.app.state.pool, project_id)
    return [dict(r) for r in rows if user.can_access(r["project_id"])]


@router.get("/daily-summary", response_model=HourlySummary)
async def daily_summary(
    request: Request,
    project_id: str | None = Query(None),
    days: int = Query(7),
    user: User = Depends(get_current_user),
) -> HourlySummary:
    if project_id is not None:
        user.ensure_access(project_id)
    days = max(1, min(days, 90))
    pool = request.app.state.pool

    yesterday = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

    summary, cleanup_rows, error_rows = await asyncio.gather(
        db.get_hourly_summary(pool, project_id, days),
        pool.fetch(
            """SELECT DISTINCT ON (project_id, site_key)
                      project_id, site_key, error_message
               FROM agent_daily_cleanup
               WHERE executed_at >= $1
               ORDER BY project_id, site_key, id DESC""",
            yesterday,
        ),
        pool.fetch(
            """SELECT DISTINCT ON (project_id, site_key)
                      project_id, site_key, success, error_count
               FROM agent_daily_error_count
               WHERE date >= $1
               ORDER BY project_id, site_key, date DESC""",
            yesterday.date(),
        ),
    )

    agent_config_path = request.app.state.settings.agent_config
    if Path(agent_config_path).exists():
        agent_config = _load_agent_config(agent_config_path)
        for site in agent_config.sites:
            entry = summary.setdefault(site.project_id, {}).setdefault(site.site_key, SiteSummaryEntry(days=[]))
            entry.has_agent = True

    for r in cleanup_rows:
        entry = summary.setdefault(r["project_id"], {}).setdefault(r["site_key"], SiteSummaryEntry(days=[]))
        entry.cleanup_ok = r["error_message"] is None

    for r in error_rows:
        entry = summary.setdefault(r["project_id"], {}).setdefault(r["site_key"], SiteSummaryEntry(days=[]))
        entry.errors_ok = r["success"] and r["error_count"] == 0

    return {pid: sites for pid, sites in summary.items() if user.can_access(pid)}
