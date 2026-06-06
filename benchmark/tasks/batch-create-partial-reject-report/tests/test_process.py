from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


SOURCE = PROJECT / "batch_import.py"


def _does_not_return_early_on_first_failure():
    text = read_text(SOURCE)
    assert 'return {"success": [], "failures":' not in text, "all-or-nothing early return detected"
    return "no all-or-nothing return detected"


def _output_sections_present():
    text = read_text(SOURCE)
    assert '"success"' in text and '"failures"' in text and '"summary"' in text, "expected output sections missing"
    return "output sections present"


def _loop_continues_after_failures():
    text = read_text(SOURCE)
    assert "continue" in text, "loop should continue after invalid records"
    return "continue present"


def run():
    public = run_checks("public", [("output_sections_present", _output_sections_present)])
    hidden = run_checks(
        "hidden",
        [
            ("does_not_return_early_on_first_failure", _does_not_return_early_on_first_failure),
            ("loop_continues_after_failures", _loop_continues_after_failures),
        ],
    )
    return emit_report("E2-LS1-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
