from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from mock_api import FakeClock, RateLimitAPI
from retry_client import fetch_cases
from verifier_lib.runtime import emit_report, print_report, run_checks


def _run_cases():
    api = RateLimitAPI({"alpha": 2, "beta": 5})
    clock = FakeClock()
    results = fetch_cases(["alpha", "beta"], api, clock, max_retries=3)
    return results, api, clock


def _timestamps_for(api, case_id):
    return [row["timestamp"] for row in api.trace if row["case_id"] == case_id]


def run():
    public = run_checks(
        "public",
        [
            ("retrieves_both_payloads", lambda: set(_run_cases()[0]) == {"alpha", "beta"} or (_ for _ in ()).throw(AssertionError("expected both cases to succeed"))),
            ("trace_has_retries", lambda: len(_run_cases()[1].trace) >= 4 or (_ for _ in ()).throw(AssertionError("expected repeated calls in trace"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("alpha_wait_honors_header", lambda: (_timestamps_for(_run_cases()[1], "alpha")[1] - _timestamps_for(_run_cases()[1], "alpha")[0]) >= 2 or (_ for _ in ()).throw(AssertionError("alpha should wait at least 2 seconds"))),
            ("beta_wait_honors_dynamic_header", lambda: (_timestamps_for(_run_cases()[1], "beta")[1] - _timestamps_for(_run_cases()[1], "beta")[0]) >= 5 or (_ for _ in ()).throw(AssertionError("beta should wait at least 5 seconds"))),
            ("payload_values_correct", lambda: _run_cases()[0]["beta"]["value"] == "payload-beta" or (_ for _ in ()).throw(AssertionError("unexpected payload value"))),
            ("bounded_retries", lambda: all(len(_timestamps_for(_run_cases()[1], case_id)) <= 4 for case_id in ("alpha", "beta")) or (_ for _ in ()).throw(AssertionError("retries should remain bounded"))),
        ],
    )
    return emit_report("E2-LS2-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
