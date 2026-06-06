from __future__ import annotations

import json
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from verifier_lib.runtime import emit_report, load_module, print_report, run_checks

SOLUTION = PROJECT / "solution.py"
OUTPUT = PROJECT / "output.json"
TRACE = PROJECT / "trace.json"


def _run_solution():
    for path in (OUTPUT, TRACE):
        if path.exists():
            path.unlink()
    module = load_module("e2_ls3_t5_solution_runtime", SOLUTION)
    result = module.main()
    output_payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    trace_payload = json.loads(TRACE.read_text(encoding="utf-8"))
    return result, output_payload, trace_payload


def run():
    _, output_payload, trace_payload = _run_solution()
    public = run_checks(
        "public",
        [
            ("retrieves_at_least_five_pages", lambda: len(trace_payload["trace"]) >= 5 or (_ for _ in ()).throw(AssertionError("expected at least 5 calls"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("includes_all_eight_pages", lambda: len(output_payload) == 80 or (_ for _ in ()).throw(AssertionError(f"expected 80 reports, got {len(output_payload)}"))),
            ("trace_has_eight_calls", lambda: len(trace_payload["trace"]) == 8 or (_ for _ in ()).throw(AssertionError(f"expected 8 calls, got {len(trace_payload['trace'])}"))),
            ("does_not_stop_at_five", lambda: trace_payload["trace"][-1]["page"] == 8 or (_ for _ in ()).throw(AssertionError("solution stopped before page 8"))),
        ],
    )
    return emit_report("E2-LS3-T5", public, hidden)


def test_t5_outcome_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
