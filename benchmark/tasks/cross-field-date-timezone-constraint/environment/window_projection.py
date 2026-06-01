from __future__ import annotations

from datetime import UTC, datetime

from timezone_defaults import DEFAULT_TIMEZONE


def parse_bound(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=DEFAULT_TIMEZONE)
    return parsed


def build_window(payload):
    window = {
        "start": parse_bound(payload["start_date"]),
        "payload": payload,
    }
    if "end_date" in payload:
        window["end"] = parse_bound(payload["end_date"])
    return window


def wall_clock_pair(window):
    return (
        window["start"].replace(tzinfo=None),
        window["end"].replace(tzinfo=None),
    )


def calendar_day_pair(window):
    return (
        window["start"].date(),
        window["end"].date(),
    )


def utc_pair(window):
    return (
        window["start"].astimezone(UTC),
        window["end"].astimezone(UTC),
    )
