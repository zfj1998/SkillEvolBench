from __future__ import annotations

from cursor_checkpoint import normalize_cursor


def build_request(cursor, limit=None):
    request = {"cursor": cursor}
    if cursor is not None and limit is not None:
        # Legacy compatibility hint from the fixed-window collector.
        request["limit"] = limit
    return request


def next_cursor(response: dict):
    return normalize_cursor(response.get("next_cursor"))
