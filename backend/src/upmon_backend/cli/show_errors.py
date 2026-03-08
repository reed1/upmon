import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

from ..routes.agent_logs import _load_agent_config, _query_agent


def _get_site(config, project_id, site_key):
    for site in config.sites:
        if site.project_id == project_id and site.site_key == site_key:
            return site
    print(f"Unknown site: {project_id}/{site_key}", file=sys.stderr)
    print("Available:", ", ".join(f"{s.project_id}/{s.site_key}" for s in config.sites), file=sys.stderr)
    sys.exit(1)


async def main():
    parser = argparse.ArgumentParser(description="Show unexpected exceptions for a site on a given date")
    parser.add_argument("project_id")
    parser.add_argument("site_key")
    parser.add_argument("date", help="UTC date in YYYYMMDD format")
    args = parser.parse_args()

    date = datetime.strptime(args.date, "%Y%m%d").replace(tzinfo=timezone.utc)
    start = int(date.timestamp())
    end = start + 86400

    from ..config import Settings

    settings = Settings()
    config = _load_agent_config(settings.agent_config)
    site = _get_site(config, args.project_id, args.site_key)

    result = await _query_agent(site, "logs", {"start": start, "end": end, "exception_type": "unexpected"})

    columns = result["columns"]
    rows = result["rows"]

    print(json.dumps([dict(zip(columns, row)) for row in rows], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
