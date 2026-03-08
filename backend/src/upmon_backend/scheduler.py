import json
import logging
import time
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .routes.agent_logs import AgentSite, _load_agent_config

logger = logging.getLogger("upmon_backend.scheduler")

_INSERT_LOG_SQL = """
INSERT INTO agent_cleanup_log
    (executed_at, project_id, site_key, agent_url, retention_days,
     status_code, deleted_count, duration_ms, error_message)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
"""


async def _cleanup_site(pool, site: AgentSite):
    executed_at = datetime.now(timezone.utc)
    start = time.monotonic()
    status_code = None
    deleted_count = None
    error = None

    try:
        payload = json.dumps(
            {
                "command": "cleanup",
                "api_key": site.agent_api_key,
                "retention_days": site.retention_days,
            }
        )
        query_params = {"q": b64encode(payload.encode()).decode()}
        verify = not site.tls_skip_verify
        async with httpx.AsyncClient(timeout=60, verify=verify) as client:
            resp = await client.get(site.agent_url, params=query_params)

        status_code = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            if data.get("error"):
                error = data["error"]
            else:
                deleted_count = data.get("result", {}).get("deleted")
        else:
            error = resp.text
    except Exception as e:
        error = str(e)

    duration_ms = int((time.monotonic() - start) * 1000)

    await pool.execute(
        _INSERT_LOG_SQL,
        executed_at,
        site.project_id,
        site.site_key,
        site.agent_url,
        site.retention_days,
        status_code,
        deleted_count,
        duration_ms,
        error,
    )

    if error:
        logger.error("Cleanup failed for %s/%s: %s", site.project_id, site.site_key, error)
    else:
        logger.info(
            "Cleanup %s/%s: deleted %d rows in %dms", site.project_id, site.site_key, deleted_count or 0, duration_ms
        )


async def run_cleanup(pool, agent_config_path: str):
    config_path = Path(agent_config_path)
    if not config_path.exists():
        logger.warning("Agent config not found at %s, skipping cleanup", config_path)
        return

    config = _load_agent_config(agent_config_path)
    logger.info("Starting agent cleanup for %d sites", len(config.sites))

    for site in config.sites:
        await _cleanup_site(pool, site)

    retain = 360 * len(config.sites)
    max_id = await pool.fetchval("SELECT MAX(id) FROM agent_cleanup_log")
    if max_id is not None:
        cutoff = max_id - retain
        if cutoff > 0:
            deleted = await pool.execute("DELETE FROM agent_cleanup_log WHERE id < $1", cutoff)
            logger.info("Cleanup log self-cleanup: %s (cutoff id %d)", deleted, cutoff)

    logger.info("Agent cleanup complete")


def create_scheduler(pool, agent_config_path: str) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_cleanup,
        trigger=CronTrigger(hour=1, minute=0, timezone="UTC"),
        id="agent_cleanup",
        replace_existing=True,
        kwargs={"pool": pool, "agent_config_path": agent_config_path},
    )

    return scheduler
