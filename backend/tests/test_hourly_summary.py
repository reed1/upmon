from datetime import date, datetime, timezone

from upmon_backend.db import HourlyRow, build_hourly_summary


def _row(project: str, site: str, hour_str: str, all_up: bool) -> HourlyRow:
    return HourlyRow(
        project_id=project,
        site_key=site,
        hour=datetime.fromisoformat(hour_str).replace(tzinfo=timezone.utc),
        all_up=all_up,
    )


def test_empty_rows_empty_result():
    assert build_hourly_summary([]) == {}


def test_single_project_single_day():
    rows = [
        _row("p1", "s1", "2025-01-15T00:00:00", True),
        _row("p1", "s1", "2025-01-15T01:00:00", False),
        _row("p1", "s1", "2025-01-15T05:00:00", True),
    ]
    result = build_hourly_summary(rows)
    days = result["p1"]["s1"]
    assert len(days) == 1
    assert days[0].day == date(2025, 1, 15)
    assert days[0].checks[0] == 1
    assert days[0].checks[1] == 0
    assert days[0].checks[2] is None
    assert days[0].checks[5] == 1


def test_multiple_projects_and_sites():
    rows = [
        _row("p1", "s1", "2025-01-15T10:00:00", True),
        _row("p2", "s2", "2025-01-15T11:00:00", False),
    ]
    result = build_hourly_summary(rows)
    assert "p1" in result
    assert "p2" in result
    assert result["p1"]["s1"][0].checks[10] == 1
    assert result["p2"]["s2"][0].checks[11] == 0


def test_hours_spanning_two_days():
    rows = [
        _row("p1", "s1", "2025-01-15T23:00:00", True),
        _row("p1", "s1", "2025-01-16T00:00:00", False),
    ]
    result = build_hourly_summary(rows)
    days = result["p1"]["s1"]
    assert len(days) == 2
    assert days[0].day == date(2025, 1, 15)
    assert days[0].checks[23] == 1
    assert days[1].day == date(2025, 1, 16)
    assert days[1].checks[0] == 0
