import asyncio
import logging

from ..config import Settings
from ..db import create_pool, run_init
from ..scheduler import create_scheduler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main():
    settings = Settings()
    pool = await create_pool(settings.database_url)
    await run_init(pool)

    # create_scheduler without .start() — safe to run alongside the live
    # scheduler since no cron triggers will fire.
    scheduler = create_scheduler(pool, settings.agent_config)
    for job in scheduler.get_jobs():
        logging.info("Running job: %s", job.id)
        await job.func(**job.kwargs)

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
