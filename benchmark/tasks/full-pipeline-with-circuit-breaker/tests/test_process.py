from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, load_module, print_report, read_text, run_checks

SOURCE = PROJECT / "breaker_client.py"


def _has_three_states():
    text = read_text(SOURCE)
    assert "CLOSED" in text and "OPEN" in text and "HALF_OPEN" in text, "expected closed/open/half-open states"
    return "has breaker states"


def _tracks_threshold_and_timeout():
    text = read_text(SOURCE)
    assert "failure_threshold" in text and "recovery_timeout" in text, "expected threshold and timeout settings"
    return "tracks threshold and timeout"


def _tracks_probe_timing():
    text = read_text(SOURCE)
    assert "next_probe_at" in text, "expected next probe timing"
    return "tracks probe timing"


def _cooldown_ignores_success_budget():
    text = read_text(SOURCE)
    assert "success_budget" not in text, "cooldown should not be shortened by recent healthy traffic"
    return "cooldown ignores success budget"


def _fail_fast_does_not_increment_failures():
    client_module = load_module("e2_ls2_t6_breaker_process", SOURCE)
    mock_module = load_module("e2_ls2_t6_mock_process", PROJECT / "mock_breaker.py")
    service = mock_module.DownstreamAPI()
    clock = mock_module.FakeClock()
    client = client_module.ResilientClient(service, failure_threshold=5, recovery_timeout=15.0)

    for ts in [0, 6, 8, 10, 12, 14]:
        clock.set(ts)
        client.get_resource(clock)

    assert client.state == client.OPEN, "client should be open after threshold failures"
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
