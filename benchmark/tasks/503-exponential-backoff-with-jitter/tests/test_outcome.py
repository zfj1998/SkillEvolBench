from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from mock_api import FakeClock, SequenceRng, UnstableAPI
from retry_client import fetch_with_retry
from verifier_lib.runtime import emit_report, print_report, run_checks


def _run_case():
    api = UnstableAPI(failures_before_success=3)
    clock = FakeClock()
    rng = SequenceRng([0.25, 0.75, 0.5])
    payload = fetch_with_retry(api, clock, rng, max_retries=5, base_delay=1.0)
    return payload, api, clock, rng


def run():
    public = run_checks(
        "public",
        [
            ("eventually_returns_payload", lambda: _run_case()[0]["payload"] == "ready" or (_ for _ in ()).throw(AssertionError("expected payload"))),
            ("multiple_attempts_recorded", lambda: len(_run_case()[1].trace) >= 4 or (_ for _ in ()).throw(AssertionError("expected retries before success"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("intervals_grow_exponentially", lambda: all(curr >= prev * 1.5 for prev, curr in zip(_run_case()[2].sleep_calls, _run_case()[2].sleep_calls[1:])) or (_ for _ in ()).throw(AssertionError("sleep intervals should grow"))),
            ("intervals_include_jitter", lambda: (_run_case()[2].sleep_calls != [1.0, 2.0, 4.0] and len({round(v, 3) for v in _run_case()[2].sleep_calls}) > 1 and len(_run_case()[3].calls) == 3) or (_ for _ in ()).throw(AssertionError("expected jittered delays"))),
            ("payload_shape_correct", lambda: _run_case()[0]["attempt"] == 4 or (_ for _ in ()).throw(AssertionError("unexpected success attempt"))),
            ("retry_bound_respected", lambda: len(_run_case()[1].trace) <= 6 or (_ for _ in ()).throw(AssertionError("retry count exceeded bound"))),
        ],
    )
    return emit_report("E2-LS2-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
