from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, run_checks

from breaker_client import ResilientClient
from mock_breaker import DownstreamAPI, FakeClock


def _drive(schedule=(0, 2, 4, 6, 8, 10, 12, 14, 20, 25, 35, 36)):
    service = DownstreamAPI()
    clock = FakeClock()
    client = ResilientClient(
        service, failure_threshold=5, recovery_timeout=15.0
    )
    results = []
    for timestamp in schedule:
        clock.set(timestamp)
        results.append(client.get_resource(clock))
    return results, service, client


def _has_three_states():
    results, _, client = _drive()
    states = {row["state"] for row in results}
    assert states <= {"closed", "open", "half_open"}, states
    assert {"closed", "open"} <= states
    assert client.state == "closed", "successful recovery probe should close"
    return "breaker exposes valid states and closes after recovery"


def _tracks_threshold_and_timeout():
    service = DownstreamAPI()
    clock = FakeClock()
    client = ResilientClient(service, failure_threshold=2, recovery_timeout=5.0)
    for timestamp in (6, 8):
        clock.set(timestamp)
        client.get_resource(clock)
    assert client.state == "open"
    calls = len(service.trace)
    clock.set(12)
    client.get_resource(clock)
    assert len(service.trace) == calls, "cooldown ended before configured timeout"
    return "threshold and recovery timeout affect runtime behavior"


def _tracks_probe_timing():
    results, service, _ = _drive()
    called_at = {row["timestamp"] for row in service.trace}
    assert 20 not in called_at and 25 not in called_at
    assert 35 in called_at
    assert results[-2]["state"] == "closed"
    return "probe is withheld during cooldown and allowed at recovery"


def _cooldown_ignores_success_budget():
    _, service, _ = _drive()
    called_at = {row["timestamp"] for row in service.trace}
    assert 20 not in called_at and 25 not in called_at
    return "recent successes do not shorten the configured cooldown"


def _fail_fast_does_not_increment_failures():
    service = DownstreamAPI()
    clock = FakeClock()
    client = ResilientClient(
        service, failure_threshold=5, recovery_timeout=15.0
    )

    for ts in [0, 6, 8, 10, 12, 14]:
        clock.set(ts)
        client.get_resource(clock)

    assert client.state == "open", "client should be open after threshold failures"
    failure_count = client.failure_count
    downstream_calls = len(service.trace)

    clock.set(20)
    client.get_resource(clock)
    client.get_resource(clock)

    assert len(service.trace) == downstream_calls, "fail-fast path should not call downstream"
    assert client.failure_count == failure_count, "fail-fast path should not add downstream failures"
    return "fail-fast does not increment failure count"


def run():
    public = run_checks("public", [("has_three_states", _has_three_states)])
    hidden = run_checks(
        "hidden",
        [
            ("tracks_threshold_and_timeout", _tracks_threshold_and_timeout),
            ("tracks_probe_timing", _tracks_probe_timing),
            ("cooldown_ignores_success_budget", _cooldown_ignores_success_budget),
            ("fail_fast_does_not_increment_failures", _fail_fast_does_not_increment_failures),
        ],
    )
    return emit_report("E2-LS2-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
