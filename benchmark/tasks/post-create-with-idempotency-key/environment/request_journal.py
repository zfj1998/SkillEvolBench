from __future__ import annotations


def note_timeout(attempt: int) -> dict:
    return {"attempt": attempt, "event": "timeout"}
