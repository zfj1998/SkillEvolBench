from __future__ import annotations

import re
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


SOURCE = PROJECT / "pipeline.py"


def _no_shortcut_none_handling():
    text = read_text(SOURCE)
    assert not re.search(r"if\s+not\s+\w+\s*:\s*\n\s*return\s+None", text), "found blanket falsy shortcut"
    return "no blanket falsy shortcut"


def _pipeline_class_exists():
    text = read_text(SOURCE)
    assert "class Pipeline" in text and "def run(" in text, "Pipeline class with run() not found"
    return "Pipeline class found"


def _stage_functions_preserved():
    text = read_text(SOURCE)
    for name in ["def parse", "def transform", "def format_output"]:
        assert name in text, f"missing stage function {name}"
    return "stage functions preserved"


def run():
    public = run_checks("public", [("pipeline_class_exists", _pipeline_class_exists)])
    hidden = run_checks(
        "hidden",
        [
            ("no_shortcut_none_handling", _no_shortcut_none_handling),
            ("stage_functions_preserved", _stage_functions_preserved),
        ],
    )
    return emit_report("E1-LS3-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
