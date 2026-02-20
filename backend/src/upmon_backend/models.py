from datetime import date, datetime

from pydantic import BaseModel


class MonitorStatus(BaseModel):
    project_id: str
    site_key: str
    url: str
    status_code: int | None
    response_ms: int
    is_up: bool
    error_type: str | None
    error_message: str | None
    last_checked_at: datetime
    last_up_at: datetime | None


class DayChecks(BaseModel):
    day: date
    checks: list[int | None]


type HourlySummary = dict[str, dict[str, list[DayChecks]]]
