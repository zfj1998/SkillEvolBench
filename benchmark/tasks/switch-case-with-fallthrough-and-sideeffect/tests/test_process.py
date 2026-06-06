from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


SOURCE = PROJECT / "src" / "processEvent.js"


def _switch_removed():
    text = read_text(SOURCE)
    assert "switch (" not in text and "switch(" not in text, "switch-case still present"
    return "switch removed"


def _mapping_present():
    text = read_text(SOURCE)
    assert "handlers" in text or "mapping" in text or "strategy" in text, "strategy mapping not found"
    return "mapping present"


def _fallthrough_modeled_explicitly():
    text = read_text(SOURCE)
    assert "USER_LOGIN" in text and "USER_ACTIVITY" in text, "fallthrough chain not modeled"
    return "fallthrough chain referenced"


def run():
    public = run_checks("public", [("switch_removed", _switch_removed)])
    hidden = run_checks(
        "hidden",
        [
            ("mapping_present", _mapping_present),
            ("fallthrough_modeled_explicitly", _fallthrough_modeled_explicitly),
        ],
    )
    return emit_report("E1-LS3-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
