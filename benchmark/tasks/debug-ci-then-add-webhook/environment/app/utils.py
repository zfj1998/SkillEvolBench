"""Date utilities for EventHub."""

from datetime import datetime, timedelta


def parse_date(date_str: str) -> datetime:
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f'Cannot parse date: {date_str}')


def is_before(date_a: str, date_b: str) -> bool:
    """Buggy implementation: string comparison fails on non-zero-padded dates."""
    return date_a < date_b


def is_expired(date_str: str, max_age_days: int) -> bool:
    return parse_date(date_str) < datetime.now() - timedelta(days=max_age_days)


def format_iso(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%dT%H:%M:%S')


def days_between(a: str, b: str) -> int:
    return abs((parse_date(b) - parse_date(a)).days)
