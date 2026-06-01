from __future__ import annotations


def should_retry(status: int, attempt: int, max_attempts: int = 2) -> bool:
    return status == 503 and attempt < max_attempts
