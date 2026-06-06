from __future__ import annotations

import json
import sys
from datetime import datetime
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
    module = load_module("e2_ls3_t6_solution_runtime", SOLUTION)
    result = module.main()
    output_payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    trace_payload = json.loads(TRACE.read_text(encoding="utf-8"))
    return result, output_payload, trace_payload


def run():
    _, output_payload, trace_payload = _run_solution()
    created = [item["created_at"] for item in output_payload]
    parsed_created = [datetime.fromisoformat(item["created_at"]) for item in output_payload]
    public = run_checks(
        "public",
        [
            ("returns_many_orders", lambda: len(output_payload) >= 100 or (_ for _ in ()).throw(AssertionError(f"expected at least 100 orders, got {len(output_payload)}"))),
            ("sorted_by_date", lambda: parsed_created == sorted(parsed_created) or (_ for _ in ()).throw(AssertionError("orders must be sorted chronologically by created_at"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("exactly_120_unique_orders", lambda: len(output_payload) == 120 and len({item["order_id"] for item in output_payload}) == 120 or (_ for _ in ()).throw(AssertionError("expected 120 unique orders"))),
            ("strictly_sorted", lambda: parsed_created == sorted(parsed_created) or (_ for _ in ()).throw(AssertionError("orders should remain in ascending chronological order"))),
            ("retry_happened_for_503", lambda: sum(1 for entry in trace_payload["trace"] if entry["region"] == "us" and entry["page"] == 3) == 2 or (_ for _ in ()).throw(AssertionError("us page 3 should be retried once"))),
            ("both_regions_paginated", lambda: {entry["region"] for entry in trace_payload["trace"] if entry["status"] == 200} == {"us", "eu"} and max(entry["page"] for entry in trace_payload["trace"] if entry["region"] == "us" and entry["status"] == 200) == 4 and max(entry["page"] for entry in trace_payload["trace"] if entry["region"] == "eu" and entry["status"] == 200) == 3 or (_ for _ in ()).throw(AssertionError("both regional APIs must be fully paginated"))),
        ],
    )
    return emit_report("E2-LS3-T6", public, hidden)


def test_t6_outcome_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
