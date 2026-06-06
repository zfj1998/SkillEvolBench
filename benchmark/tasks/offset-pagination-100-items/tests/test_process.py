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
OFFSET_PLAN = PROJECT / "offset_plan.py"
USER_BUFFER = PROJECT / "user_buffer.py"


def _tree():
    return ast.parse(read_text(SOURCE))


def _source():
    return read_text(SOURCE)


def _has_loop():
    tree = _tree()
    assert any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)), "expected a pagination loop"
    return "loop found"


def _has_dedup_logic():
    tree = ast.parse(read_text(USER_BUFFER))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    has_set_call = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"set", "dict"}
        for node in ast.walk(tree)
    )
    assert "seen_ids" in names or has_set_call, "expected dedup logic"
    return "dedup logic found"


def _uses_requested_stride():
    text = read_text(OFFSET_PLAN).replace(" ", "")
    assert "current_offset+request_limit" in text, "expected offset advance based on requested page size"
    return "requested stride used"


def _not_hardcoded_five_pages():
    text = _source().replace(" ", "")
    disallowed = ["range(5)", "[0,20,40,60,80]"]
    assert not any(pattern in text for pattern in disallowed), "solution should not hardcode five pages"
    return "no five-page hardcoding"


def run():
    public = run_checks("public", [("has_loop", _has_loop)])
    hidden = run_checks(
        "hidden",
        [
            ("has_dedup_logic", _has_dedup_logic),
            ("uses_requested_stride", _uses_requested_stride),
            ("not_hardcoded_five_pages", _not_hardcoded_five_pages),
        ],
    )
    return emit_report("E2-LS3-T1", public, hidden)


def test_t1_process_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
