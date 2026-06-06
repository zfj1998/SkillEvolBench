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


def _source():
    return read_text(SOURCE)


def _rechecks_metadata_or_has_more():
    text = _source()
    assert "has_more" in text or text.count("total_pages") >= 2, "expected repeated pagination-state checks"
    return "repeated pagination-state checks found"


def _not_hardcoded_to_first_total_pages():
    text = _source().replace(" ", "")
    assert "range(2,total_pages+1)" not in text and "range(5)" not in text, "solution should not trust the first total_pages value"
    return "no early total_pages hardcoding"


def run():
    public = run_checks("public", [("rechecks_metadata_or_has_more", _rechecks_metadata_or_has_more)])
    hidden = run_checks("hidden", [("not_hardcoded_to_first_total_pages", _not_hardcoded_to_first_total_pages)])
    return emit_report("E2-LS3-T5", public, hidden)


def test_t5_process_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
