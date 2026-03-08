import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import SELF_CLEANUP_RETAIN_PER_SITE
from ..routes.agent_logs import AgentSite, _load_agent_config, _query_agent

logger = logging.getLogger("upmon_backend.jobs.error_count")

_INSERT_ERROR_COUNT_SQL = """
INSERT INTO agent_daily_error_count
    (date, project_id, site_key, success, agent_error, error_count, recorded_at)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (project_id, site_key, date) DO UPDATE SET
    success = EXCLUDED.success,
    agent_error = EXCLUDED.agent_error,
    error_count = EXCLUDED.error_count,
    recorded_at = EXCLUDED.recorded_at
"""


async def _count_errors_for_site(pool, site: AgentSite, yesterday):
    start_epoch = int(datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc).timestamp())
    end_epoch = start_epoch + 86400

    error_count = None
    agent_error = None

    try:
        result = await _query_agent(site, "error_count", {"start": start_epoch, "end": end_epoch})
        rows = result.get("rows", [])
        if rows and rows[0]:
            error_count = rows[0][0]
        else:
            agent_error = "Agent returned no rows for error_count query"
    except Exception as e:
        agent_error = str(e)
        logger.error("Error count failed for %s/%s: %s", site.project_id, site.site_key, e)

    await pool.execute(
        _INSERT_ERROR_COUNT_SQL,
        yesterday,
        site.project_id,
        site.site_key,
        agent_error is None,
        agent_error,
        error_count,
        datetime.now(timezone.utc),
    )

    if error_count is not None:
        logger.info("Error count %s/%s on %s: %d", site.project_id, site.site_key, yesterday, error_count)


async def run_error_count(pool, agent_config_path: str):
    config_path = Path(agent_config_path)
    if not config_path.exists():
        logger.warning("Agent config not found at %s, skipping error count", config_path)
        return

    config = _load_agent_config(agent_config_path)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    logger.info("Starting error count for %d sites, date=%s", len(config.sites), yesterday)

    for site in config.sites:
        await _count_errors_for_site(pool, site, yesterday)

    retain = SELF_CLEANUP_RETAIN_PER_SITE * len(config.sites)
    max_id = await pool.fetchval("SELECT MAX(id) FROM agent_daily_error_count")
    if max_id is not None:
        cutoff = max_id - retain
        if cutoff > 0:
            deleted = await pool.execute("DELETE FROM agent_daily_error_count WHERE id < $1", cutoff)
            logger.info("Error count self-cleanup: %s (cutoff id %d)", deleted, cutoff)

    logger.info("Error count complete")
