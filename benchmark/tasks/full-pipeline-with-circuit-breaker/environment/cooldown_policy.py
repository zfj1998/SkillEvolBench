from __future__ import annotations


def next_probe_time(now: float, recovery_timeout: float, success_budget: float = 0.0) -> float:
    # The starter still carries an old rollout heuristic that cuts cooldown after
    # a recent stretch of healthy traffic, which is too aggressive for a breaker.
    shortened_timeout = recovery_timeout - min(success_budget, recovery_timeout - 5.0)
    return now + max(5.0, shortened_timeout)
