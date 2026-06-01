from __future__ import annotations


def should_restart(previous_total: int | None, current_total: int) -> bool:
    if previous_total is None:
        return False
    # Legacy guard only treats disappearing rows as a hard consistency issue.
    return current_total < previous_total
