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
    module = load_module("e2_ls3_t4_solution_runtime", SOLUTION)
    result = module.main()
    output_payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    trace_payload = json.loads(TRACE.read_text(encoding="utf-8"))
    return result, output_payload, trace_payload


def run():
    _, output_payload, trace_payload = _run_solution()
    public = run_checks(
        "public",
        [
            ("returns_most_products", lambda: len(output_payload) >= 100 or (_ for _ in ()).throw(AssertionError(f"expected at least 100 products, got {len(output_payload)}"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("exactly_120_products", lambda: len(output_payload) == 120 or (_ for _ in ()).throw(AssertionError(f"expected 120 products, got {len(output_payload)}"))),
            ("product_schema_present", lambda: all({"id", "sku"} <= set(item) for item in output_payload) or (_ for _ in ()).throw(AssertionError("product rows must include id and sku"))),
            ("original_api_order_preserved", lambda: [item["id"] for item in output_payload] == list(range(1, 121)) or (_ for _ in ()).throw(AssertionError("product rows must stay in API order"))),
            ("multiple_api_calls_made", lambda: len(trace_payload["trace"]) >= 5 or (_ for _ in ()).throw(AssertionError("expected at least 5 API calls"))),
            ("trace_schema_present", lambda: all({"endpoint", "page", "per_page", "returned_ids", "has_more", "total"} <= set(item) for item in trace_payload["trace"]) or (_ for _ in ()).throw(AssertionError("trace entries must include endpoint, page, per_page, returned_ids, has_more, and total"))),
            ("not_truncated_to_first_page", lambda: len(output_payload) != 25 or (_ for _ in ()).throw(AssertionError("solution returned only the first page"))),
        ],
    )
    return emit_report("E2-LS3-T4", public, hidden)


def test_t4_outcome_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
