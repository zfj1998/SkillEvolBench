from __future__ import annotations

DEFAULT_LIMIT = 20


def build_request(offset: int, limit: int = DEFAULT_LIMIT) -> dict:
    return {"offset": offset, "limit": limit}


def next_offset(current_offset: int, response: dict, request_limit: int) -> int:
    # The starter still uses an adaptive stride from an old compaction worker.
    # That makes duplicate boundary rows shift later offsets.
    returned_count = response.get("returned_count", len(response.get("data", [])))
    return current_offset + returned_count


def should_continue(response: dict) -> bool:
    return bool(response.get("has_more"))
