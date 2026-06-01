from __future__ import annotations


MAX_BUDGETED_WAIT = 2


def should_retry(status: int, attempts: int, max_retries: int) -> bool:
    return status == 429 and attempts < max_retries


def parse_retry_after(headers: dict[str, str]) -> int:
    return int(headers.get("Retry-After", "0"))


def compute_wait_seconds(headers: dict[str, str], case_id: str) -> int:
    retry_after = parse_retry_after(headers)
    # The old worker budgeted long waits down to two seconds so one case could
    # not monopolize the process. That logic is no longer correct for this API.
    return min(retry_after, MAX_BUDGETED_WAIT)
