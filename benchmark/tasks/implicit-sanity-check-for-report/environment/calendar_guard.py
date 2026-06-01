from __future__ import annotations

from datetime import date, timedelta

from sales_cleaning import normalize_date


def expected_march_days() -> list[str]:
    current = date(2024, 3, 1)
    end = date(2024, 3, 31)
    days = []
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def observed_days_from_raw(rows: list[dict[str, object]]) -> list[str]:
    return sorted({normalize_date(row["date"]) for row in rows if normalize_date(row["date"])})


def missing_days(rows: list[dict[str, object]]) -> list[str]:
    observed = set(observed_days_from_raw(rows))
    return [day for day in expected_march_days() if day not in observed]
