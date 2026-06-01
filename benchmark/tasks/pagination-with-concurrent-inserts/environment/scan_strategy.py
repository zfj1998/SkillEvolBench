from __future__ import annotations

DEFAULT_LIMIT = 20


def initial_request() -> dict:
    return {"offset": 0, "limit": DEFAULT_LIMIT}


def next_offset(offset: int, limit: int = DEFAULT_LIMIT) -> int:
    return offset + limit
