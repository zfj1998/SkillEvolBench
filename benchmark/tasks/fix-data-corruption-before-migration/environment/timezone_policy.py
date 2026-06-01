"""Timezone policy helpers for migration and reporting."""
from zoneinfo import ZoneInfo


def local_zone():
    return ZoneInfo("America/New_York")


def attach_local_timezone(value):
    return value.replace(tzinfo=local_zone())
