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
    module = load_module("e2_ls3_t2_solution_runtime", SOLUTION)
    result = module.main()
    output_payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    trace_payload = json.loads(TRACE.read_text(encoding="utf-8"))
    return result, output_payload, trace_payload


def run():
    _, output_payload, trace_payload = _run_solution()
    public = run_checks(
        "public",
        [
            ("returns_most_events", lambda: len(output_payload) >= 70 or (_ for _ in ()).throw(AssertionError(f"expected at least 70 events, got {len(output_payload)}"))),
            ("contains_first_and_last_ids", lambda: ({item["id"] for item in output_payload} >= {1, 80}) or (_ for _ in ()).throw(AssertionError("result should include ids 1 and 80"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("exactly_80_unique_events", lambda: len(output_payload) == 80 and len({item["id"] for item in output_payload}) == 80 or (_ for _ in ()).throw(AssertionError("expected exactly 80 unique events"))),
            ("boundary_duplicates_exercised", lambda: sum(len(entry["returned_ids"]) for entry in trace_payload["trace"]) > len({event_id for entry in trace_payload["trace"] for event_id in entry["returned_ids"]}) or (_ for _ in ()).throw(AssertionError("mock stream should include repeated boundary ids"))),
            ("cursor_chain_respected", lambda: all(trace_payload["trace"][index + 1]["cursor"] == trace_payload["trace"][index]["next_cursor"] for index in range(len(trace_payload["trace"]) - 1)) or (_ for _ in ()).throw(AssertionError("request cursors should match the opaque next_cursor values returned by the API"))),
            ("no_offset_or_limit_params", lambda: all(not set(entry["params"]).intersection({"offset", "limit"}) for entry in trace_payload["trace"]) or (_ for _ in ()).throw(AssertionError("offset/limit params should not be used"))),
            ("stops_after_null_cursor", lambda: trace_payload["trace"][-1]["next_cursor"] is None and len(trace_payload["trace"]) == 5 or (_ for _ in ()).throw(AssertionError("solution should stop after next_cursor becomes null"))),
        ],
    )
    return emit_report("E2-LS3-T2", public, hidden)


def test_t2_outcome_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
