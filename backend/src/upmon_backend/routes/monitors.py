from fastapi import APIRouter, Depends, Query, Request

from .. import db
from ..auth import require_api_key
from ..models import HourlySummary, MonitorStatus

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
    return await db.get_hourly_summary(request.app.state.pool, project_id, days)
