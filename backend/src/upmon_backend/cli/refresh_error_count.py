import argparse
import asyncio
import logging
from datetime import datetime, timezone

from ..config import Settings
from ..db import create_pool, run_init
from ..jobs.error_count import _count_errors_for_site
from ..routes.agent_logs import _load_agent_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main():
    parser = argparse.ArgumentParser(
        description="Re-query agent error counts for a given UTC date and update the database"
    )
    parser.add_argument("date", help="UTC date in YYYYMMDD format")
    parser.add_argument("project_id", nargs="?", help="Project ID (omit to refresh all sites)")
    parser.add_argument("site_key", nargs="?", help="Site key (requires project_id)")
    args = parser.parse_args()

    date = datetime.strptime(args.date, "%Y%m%d").replace(tzinfo=timezone.utc).date()

    if args.site_key and not args.project_id:
        parser.error("site_key requires project_id")

    settings = Settings()
    config = _load_agent_config(settings.agent_config)

    if args.project_id:
        sites = [s for s in config.sites if s.project_id == args.project_id]
        if args.site_key:
            sites = [s for s in sites if s.site_key == args.site_key]
        if not sites:
            label = f"{args.project_id}/{args.site_key}" if args.site_key else args.project_id
            available = ", ".join(f"{s.project_id}/{s.site_key}" for s in config.sites)
            parser.error(f"Unknown site: {label}. Available: {available}")
    else:
        sites = config.sites

    pool = await create_pool(settings.database_url)
    await run_init(pool)

    logging.info("Refreshing error count for %d site(s), date=%s", len(sites), date)
    for site in sites:
        await _count_errors_for_site(pool, site, date)

    await pool.close()
    logging.info("Done")


if __name__ == "__main__":
    asyncio.run(main())
