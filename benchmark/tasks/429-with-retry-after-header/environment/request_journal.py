from __future__ import annotations


def journal_attempt(case_id: str, attempts: int, response: dict) -> dict:
    return {
        "case_id": case_id,
        "attempts": attempts,
        "status": response["status"],
        "retry_after": response["headers"].get("Retry-After"),
    }
