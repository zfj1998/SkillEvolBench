from __future__ import annotations


def build_retry_snapshot(attempt: int, status: int) -> dict:
    return {
        "attempt": attempt,
        "status": status,
    }
