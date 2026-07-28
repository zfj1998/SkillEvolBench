from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, load_module, print_report, run_checks

SOURCE = PROJECT / "solution.py"
MERGE_INDEX = PROJECT / "merge_index.py"
ORDERING_POLICY = PROJECT / "ordering_policy.py"


def _run():
    for path in (PROJECT / "output.json", PROJECT / "trace.json"):
        if path.exists():
            path.unlink()
    module = load_module("e2_ls3_t6_process_runtime", SOURCE)
    module.main()
    output = json.loads((PROJECT / "output.json").read_text(encoding="utf-8"))
    trace = json.loads((PROJECT / "trace.json").read_text(encoding="utf-8"))
    return output, trace["trace"]


def _paginates_both_regions():
    _, trace = _run()
    successful = [row for row in trace if row["status"] == 200]
    assert {row["region"] for row in successful} == {"us", "eu"}
    assert max(row["page"] for row in successful if row["region"] == "us") == 4
    assert max(row["page"] for row in successful if row["region"] == "eu") == 3
    return "both regions are fully paginated"


def _has_retry_logic():
    _, trace = _run()
    page_three = [
        row for row in trace
        if row["region"] == "us" and row["page"] == 3
    ]
    assert len(page_three) == 2
    assert [row["status"] for row in page_three] == [503, 200]
    return "transient 503 is retried once"


def _dedups_and_sorts():
    output, _ = _run()
    assert len(output) == len({row["order_id"] for row in output}) == 120
    timestamps = [datetime.fromisoformat(row["created_at"]) for row in output]
    assert timestamps == sorted(timestamps)
    return "output is deduplicated and chronologically sorted"


def _merge_uses_business_key():
    output, _ = _run()
    assert len({row["order_id"] for row in output}) == len(output)
    return "business order IDs are unique across merged regions"


def _uses_temporal_sort_key():
    output, _ = _run()
    timestamps = [datetime.fromisoformat(row["created_at"]) for row in output]
    assert timestamps == sorted(timestamps)
    return "timezone-aware timestamps are sorted chronologically"


def run():
    public = run_checks("public", [("paginates_both_regions", _paginates_both_regions)])
    hidden = run_checks(
        "hidden",
        [
            ("has_retry_logic", _has_retry_logic),
            ("dedups_and_sorts", _dedups_and_sorts),
            ("merge_uses_business_key", _merge_uses_business_key),
            ("uses_temporal_sort_key", _uses_temporal_sort_key),
        ],
    )
    return emit_report("E2-LS3-T6", public, hidden)


def test_t6_process_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
