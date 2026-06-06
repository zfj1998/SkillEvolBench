from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from client import process_requests
from verifier_lib.runtime import emit_report, print_report, run_checks


REQUESTS = PROJECT / "requests.json"


def _result():
    return process_requests(REQUESTS)


def run():
    public = run_checks(
        "public",
        [
            ("four_successes", lambda: len(_result()["successes"]) == 4 or (_ for _ in ()).throw(AssertionError("expected 4 successful requests"))),
            ("failure_objects_exist", lambda: bool(_result()["failures"]) or (_ for _ in ()).throw(AssertionError("expected failures list"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("double_fault_reports_two_errors", lambda: len(next(item for item in _result()["failures"] if item["index"] == 9)["errors"]) == 2 or (_ for _ in ()).throw(AssertionError("request #10 should report 2 errors"))),
            ("boundary_values_accepted", lambda: {item["forecast_days"] for item in _result()["successes"]} >= {1, 14} or (_ for _ in ()).throw(AssertionError("days=1 and days=14 should be accepted"))),
            ("trace_contains_only_valid_calls", lambda: len(_result()["trace"]) == 4 or (_ for _ in ()).throw(AssertionError("trace should contain only 4 valid calls"))),
            ("error_shape_has_value_expected", lambda: all("value" in err and "expected" in err for item in _result()["failures"] for err in item["errors"]) or (_ for _ in ()).throw(AssertionError("error objects should include value and expected"))),
            ("exactly_six_failures", lambda: len(_result()["failures"]) == 6 or (_ for _ in ()).throw(AssertionError(f"expected 6 failures, got {len(_result()['failures'])}"))),
        ],
    )
    return emit_report("E2-LS1-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
