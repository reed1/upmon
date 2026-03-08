import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import require_api_key

logger = logging.getLogger("upmon_backend.errors")

router = APIRouter(
    prefix="/api/v1/errors",
    dependencies=[Depends(require_api_key)],
)


def _parse_date(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y%m%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {raw}, expected yyyymmdd")


@router.get("")
async def get_errors(
    request: Request,
    date: str = Query(description="Date in yyyymmdd format (UTC, must be a completed past day)"),
) -> dict:
    parsed = _parse_date(date)

    today_utc = datetime.now(timezone.utc).date()
    if parsed >= today_utc:
        raise HTTPException(status_code=400, detail="Date must be a fully completed day (before today UTC)")

    pool = request.app.state.pool
    rows = await pool.fetch(
        """SELECT project_id, site_key, success, agent_error, error_count
           FROM agent_daily_error_count
           WHERE date = $1""",
        parsed,
    )

    total_errors = 0
    sites = {}
    for r in rows:
        key = f"{r['project_id']}/{r['site_key']}"
        if not r["success"]:
            sites[key] = {"success": False, "agent_error": r["agent_error"], "error_count": None}
        else:
            count = r["error_count"] or 0
            total_errors += count
            sites[key] = {"success": True, "error_count": count}

    return {"date": date, "total_errors": total_errors, "sites": sites}
