from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import mock_api
from pipeline import run_pipeline
from verifier_lib.runtime import emit_report, print_report, run_checks


QUERY = PROJECT / "query.txt"


def _result():
    mock_api.TRACE.clear()
    return run_pipeline(QUERY)


def _trace():
    _result()
    return list(mock_api.TRACE)


def run():
    public = run_checks(
        "public",
        [
            ("report_non_empty", lambda: _result()["count"] > 0 or (_ for _ in ()).throw(AssertionError("report should be non-empty"))),
            ("rows_present", lambda: bool(_result()["rows"]) or (_ for _ in ()).throw(AssertionError("rows missing"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("state_code_normalized", lambda: _trace()[0]["region_code"] == "CA" or (_ for _ in ()).throw(AssertionError(f"expected CA, got {_trace()[0].get('region_code')!r}"))),
            ("date_range_complete", lambda: _trace()[0]["start_date"] == "2025-03-01" and _trace()[0]["end_date"] == "2025-03-31" or (_ for _ in ()).throw(AssertionError(f"unexpected date range: {_trace()[0]!r}"))),
            ("amount_descending", lambda: _result()["rows"][0]["amount"] >= _result()["rows"][-1]["amount"] or (_ for _ in ()).throw(AssertionError("rows should be sorted descending"))),
            ("summary_fields_present", lambda: {"count", "total_amount", "average_amount"} <= _result().keys() or (_ for _ in ()).throw(AssertionError("summary fields missing"))),
            ("trace_uses_normalized_api_contract", lambda: {"region_code", "sort_by", "sort_order"} <= _trace()[0].keys() or (_ for _ in ()).throw(AssertionError(f"normalized api keys missing: {_trace()[0]!r}"))),
        ],
    )
    return emit_report("E2-LS1-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
