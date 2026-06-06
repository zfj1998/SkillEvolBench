from __future__ import annotations

import ast
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


def _reads_pagination_signal():
    text = _source()
    assert "has_more" in text or "total" in text, "expected pagination signal handling"
    return "pagination signal handled"


def _loops_until_complete():
    tree = ast.parse(_source())
    assert any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)), "expected a loop for complete retrieval"
    return "loop found"


def run():
    public = run_checks("public", [("reads_pagination_signal", _reads_pagination_signal)])
    hidden = run_checks("hidden", [("loops_until_complete", _loops_until_complete)])
    return emit_report("E2-LS3-T4", public, hidden)


def test_t4_process_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
