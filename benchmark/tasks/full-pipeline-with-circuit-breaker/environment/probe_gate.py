from __future__ import annotations

from breaker_state import BreakerState


def should_fail_fast(state: BreakerState, now: float) -> bool:
    return state.mode == "open" and now < state.next_probe_at


def should_probe(state: BreakerState, now: float) -> bool:
    return state.mode == "open" and now >= state.next_probe_at and not state.probe_in_flight


def begin_probe(state: BreakerState) -> None:
    state.mode = "half_open"
    state.probe_in_flight = True

