from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .jobs.cleanup import run_cleanup
from .jobs.error_count import run_error_count


def create_scheduler(pool, agent_config_path: str) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_cleanup,
        trigger=CronTrigger(hour=1, minute=0, timezone="UTC"),
        id="agent_cleanup",
        replace_existing=True,
        kwargs={"pool": pool, "agent_config_path": agent_config_path},
    )

    scheduler.add_job(
        run_error_count,
        trigger=CronTrigger(hour=1, minute=0, timezone="UTC"),
        id="agent_error_count",
        replace_existing=True,
        kwargs={"pool": pool, "agent_config_path": agent_config_path},
    )

    return scheduler
