import asyncio
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_api_key
from .agent_logs import AgentConfig, _parse_json_columns, _query_agent, get_agent_config

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
    date: str = Query(description="Date in yyyymmdd format (UTC, must be a completed past day)"),
    config: AgentConfig = Depends(get_agent_config),
) -> dict:
    parsed = _parse_date(date)

    today_utc = datetime.now(timezone.utc).date()
    if parsed >= today_utc:
        raise HTTPException(status_code=400, detail="Date must be a fully completed day (before today UTC)")

    start_epoch = int(datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc).timestamp())
    end_epoch = start_epoch + 86400

    sql = """
        SELECT * FROM access_log
        WHERE epoch_sec >= ? AND epoch_sec < ?
          AND exception_is_unexpected = 1
        ORDER BY epoch_sec DESC
    """
    bindings = [start_epoch, end_epoch]

    results = await asyncio.gather(*(_query_agent(site, sql, bindings) for site in config.sites))

    columns = results[0]["columns"]
    total_errors = 0
    sites = {}
    for site, result in zip(config.sites, results):
        key = f"{site.project_id}/{site.site_key}"
        rows = _parse_json_columns(result)["rows"]
        total_errors += len(rows)
        sites[key] = rows

    return {"date": date, "total_errors": total_errors, "columns": columns, "sites": sites}
