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
    module = load_module("e2_ls3_t3_solution_runtime", SOLUTION)
    result = module.main()
    output_payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    trace_payload = json.loads(TRACE.read_text(encoding="utf-8"))
    return result, output_payload, trace_payload


def run():
    _, output_payload, trace_payload = _run_solution()
    output_ids = [item["id"] for item in output_payload]
    public = run_checks(
        "public",
        [
            ("returns_at_least_initial_size", lambda: len(output_payload) >= 100 or (_ for _ in ()).throw(AssertionError(f"expected at least 100 orders, got {len(output_payload)}"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("exactly_105_orders", lambda: len(output_payload) == 105 or (_ for _ in ()).throw(AssertionError(f"expected 105 orders, got {len(output_payload)}"))),
            ("no_missing_ids", lambda: output_ids == list(range(1, 106)) or (_ for _ in ()).throw(AssertionError("expected ids 1..105 with no gaps"))),
            ("no_duplicates", lambda: len(output_ids) == len(set(output_ids)) or (_ for _ in ()).throw(AssertionError("duplicate ids found"))),
            ("adapted_to_data_change", lambda: any(entry["mode"] == "cursor" for entry in trace_payload["trace"]) or any(entry["total"] != trace_payload["trace"][0]["total"] for entry in trace_payload["trace"]) or (_ for _ in ()).throw(AssertionError("solution must adapt to the changing dataset"))),
        ],
    )
    return emit_report("E2-LS3-T3", public, hidden)


def test_t3_outcome_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
