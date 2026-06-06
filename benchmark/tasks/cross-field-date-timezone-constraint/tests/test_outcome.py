from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from search_client import process_queries
from verifier_lib.runtime import emit_report, print_report, run_checks


QUERIES = PROJECT / "queries.json"


def _result():
    return process_queries(QUERIES)


def _rejected_indexes():
    return {item["index"] for item in _result()["rejected"]}


def _accepted_count():
    return len(_result()["accepted"])


def _utc_error_reported():
    for item in _result()["rejected"]:
        for error in item.get("errors", []):
            if "UTC" in str(error.get("error", "")) or "utc" in str(error.get("payload", "")).lower():
                return "UTC-normalized error reported"
    raise AssertionError("expected a rejection to reference UTC-normalized comparison")


def run():
    public = run_checks(
        "public",
        [
            ("obvious_invalid_rejected", lambda: 2 in _rejected_indexes() or (_ for _ in ()).throw(AssertionError("obvious invalid range should be rejected"))),
            ("valid_requests_sent", lambda: _accepted_count() >= 4 or (_ for _ in ()).throw(AssertionError("expected several accepted requests"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("cross_timezone_trap_rejected", lambda: 3 in _rejected_indexes() or (_ for _ in ()).throw(AssertionError("cross-timezone trap should be rejected"))),
            ("utc_error_reported", _utc_error_reported),
            ("equality_allowed", lambda: 5 not in _rejected_indexes() or (_ for _ in ()).throw(AssertionError("equal timestamps should be allowed"))),
            ("missing_end_date_allowed", lambda: 6 not in _rejected_indexes() or (_ for _ in ()).throw(AssertionError("missing optional end_date should be allowed"))),
            ("dst_overlap_trap_rejected", lambda: 8 in _rejected_indexes() or (_ for _ in ()).throw(AssertionError("DST overlap trap should be rejected"))),
        ],
    )
    return emit_report("E2-LS1-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
