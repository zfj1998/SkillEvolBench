from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

SOURCE = PROJECT / "solution.py"
MERGE_INDEX = PROJECT / "merge_index.py"
ORDERING_POLICY = PROJECT / "ordering_policy.py"


def _source():
    return read_text(SOURCE)


def _paginates_both_regions():
    text = _source()
    assert '"us"' in text and '"eu"' in text, "expected both regional APIs to be handled"
    return "both regions referenced"


def _has_retry_logic():
    text = _source()
    assert "503" in text and ("attempt" in text or "while True" in text or "for _ in range" in text), "expected retry logic for 503"
    return "retry logic found"


def _dedups_and_sorts():
    text = _source()
    assert ("setdefault" in text or "seen" in text or "set(" in text) and "sorted(" in text, "expected deduplication and sorting"
    return "dedup and sort found"


def _merge_uses_business_key():
    text = read_text(MERGE_INDEX)
    assert 'source_region' not in text, "merge key should not depend on source region"
    assert 'order["order_id"]' in text or "order['order_id']" in text, "expected business-order id merge key"
    return "business merge key found"


def _uses_temporal_sort_key():
    text = read_text(ORDERING_POLICY)
    assert "fromisoformat" in text or "dateutil" in text or "parsedate" in text, "ordering should parse timestamps instead of sorting raw strings"
    return "temporal sort key found"


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
