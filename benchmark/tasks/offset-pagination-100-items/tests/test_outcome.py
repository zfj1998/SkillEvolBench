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
    module = load_module("e2_ls3_t1_solution_runtime", SOLUTION)
    result = module.main()
    output_payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    trace_payload = json.loads(TRACE.read_text(encoding="utf-8"))
    return result, output_payload, trace_payload


def run():
    _, output_payload, trace_payload = _run_solution()
    public = run_checks(
        "public",
        [
            ("returns_many_users", lambda: len(output_payload) >= 95 or (_ for _ in ()).throw(AssertionError(f"expected at least 95 users, got {len(output_payload)}"))),
            ("contains_first_and_last_ids", lambda: ({item["id"] for item in output_payload} >= {1, 100}) or (_ for _ in ()).throw(AssertionError("result should include ids 1 and 100"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("exactly_100_unique_users", lambda: len(output_payload) == 100 and len({item["id"] for item in output_payload}) == 100 or (_ for _ in ()).throw(AssertionError("expected exactly 100 unique users"))),
            ("exactly_five_calls", lambda: len(trace_payload["trace"]) == 5 or (_ for _ in ()).throw(AssertionError(f"expected 5 API calls, got {len(trace_payload['trace'])}"))),
            ("offset_sequence_correct", lambda: [entry["offset"] for entry in trace_payload["trace"]] == [0, 20, 40, 60, 80] or (_ for _ in ()).throw(AssertionError("offset sequence should be 0,20,40,60,80"))),
            ("duplicate_removed", lambda: trace_payload["trace"][2]["returned_ids"][0] == 40 and [item["id"] for item in output_payload].count(40) == 1 or (_ for _ in ()).throw(AssertionError("duplicate id should be removed"))),
            ("original_order_preserved", lambda: [item["id"] for item in output_payload] == list(range(1, 101)) or (_ for _ in ()).throw(AssertionError("users should remain in original order"))),
        ],
    )
    return emit_report("E2-LS3-T1", public, hidden)


def test_t1_outcome_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
