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
GUARD = PROJECT / "consistency_guard.py"
BUFFER = PROJECT / "order_buffer.py"


def _source():
    return read_text(SOURCE)


def _tree():
    return ast.parse(_source())


def _detects_change_or_uses_cursor():
    text = _source()
    assert "cursor" in text or "total" in text, "expected cursor usage or total-change handling"
    return "change adaptation present"


def _has_dedup_logic():
    tree = ast.parse(read_text(BUFFER))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    has_set_call = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"set", "dict"}
        for node in ast.walk(tree)
    )
    assert "seen_ids" in names or has_set_call, "expected dedup logic"
    return "dedup logic found"


def _validates_final_count():
    text = _source().replace(" ", "")
    assert "len(orders)!=" in text or "raiseValueError" in text, "expected a final completeness check"
    return "final count validation found"


def _detects_total_growth():
    text = read_text(GUARD).replace(" ", "")
    assert "current_total>previous_total" in text or "current_total!=previous_total" in text, "expected total-growth detection"
    return "total growth detection found"


def run():
    public = run_checks("public", [("detects_change_or_uses_cursor", _detects_change_or_uses_cursor)])
    hidden = run_checks(
        "hidden",
        [
            ("has_dedup_logic", _has_dedup_logic),
            ("detects_total_growth", _detects_total_growth),
            ("validates_final_count", _validates_final_count),
        ],
    )
    return emit_report("E2-LS3-T3", public, hidden)


def test_t3_process_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
