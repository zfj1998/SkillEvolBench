"""Helpers for report generation."""
from zoneinfo import ZoneInfo

from config import REPORT_TZ


def _to_report_timezone(value):
    return value.astimezone(ZoneInfo(REPORT_TZ))


def serialize_event(record):
    local_value = _to_report_timezone(record["updated_at"])
    return {
        "id": record["id"],
        "name": record["name"],
        "timestamp": local_value.isoformat(),
        "hour": local_value.hour,
    }
