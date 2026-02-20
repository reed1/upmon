from dataclasses import dataclass
from datetime import datetime

import asyncpg

from .models import DayChecks, HourlySummary


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, min_size=1, max_size=5)


async def get_monitor_statuses(
    pool: asyncpg.Pool, project_id: str | None
) -> list[dict]:
    return await pool.fetch(
        """SELECT project_id, site_key, url, status_code, response_ms,
                  is_up, error_type, error_message, last_checked_at, last_up_at
           FROM monitor_status
           WHERE ($1::text IS NULL OR project_id = $1)
           ORDER BY project_id, site_key""",
        project_id,
    )


@dataclass
class HourlyRow:
    project_id: str
    site_key: str
    hour: datetime
    all_up: bool


def build_hourly_summary(rows: list[HourlyRow]) -> HourlySummary:
    result: dict[str, dict[str, list[DayChecks]]] = {}

    for row in rows:
        date = row.hour.date()
        hour_idx = row.hour.hour

        days_vec = result.setdefault(row.project_id, {}).setdefault(
            row.site_key, []
        )

        if days_vec and days_vec[-1].day == date:
            day_entry = days_vec[-1]
        else:
            day_entry = DayChecks(day=date, checks=[None] * 24)
            days_vec.append(day_entry)

        day_entry.checks[hour_idx] = 1 if row.all_up else 0

    return result


async def get_hourly_summary(
    pool: asyncpg.Pool, project_id: str | None, days: int
) -> HourlySummary:
    rows = await pool.fetch(
        """SELECT project_id, site_key,
                  time_bucket('1 hour', checked_at) AS hour,
                  bool_and(is_up) AS all_up
           FROM monitor_checks
           WHERE checked_at > NOW() - make_interval(days => $1)
             AND ($2::text IS NULL OR project_id = $2)
           GROUP BY project_id, site_key, hour
           ORDER BY project_id, site_key, hour""",
        days,
        project_id,
    )

    hourly_rows = [
        HourlyRow(
            project_id=r["project_id"],
            site_key=r["site_key"],
            hour=r["hour"],
            all_up=r["all_up"],
        )
        for r in rows
    ]

    return build_hourly_summary(hourly_rows)
