from __future__ import annotations


from breaker_state import BreakerState


def snapshot_state(state: BreakerState) -> dict:
    return {
        "state": state.mode,
        "failure_count": state.failure_streak,
        "next_probe_at": state.next_probe_at,
        "probe_in_flight": state.probe_in_flight,
        "recent_success_budget": round(state.recent_success_budget, 2),
        "last_status": state.last_status,
    }
