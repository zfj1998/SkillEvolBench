from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


SOURCE = PROJECT / "transactions.py"


def _pipeline_order_present():
    text = read_text(SOURCE)
    assert text.index("enrich(") < text.index("normalize(") < text.index("send_transaction"), "pipeline order should be enrich -> normalize -> call"
    return "pipeline order found"


def _fallback_for_null_timezone():
    text = read_text(SOURCE)
    assert "UTC" in text or "timezone" in text and "or" in text, "null timezone fallback not found"
    return "timezone fallback marker present"


def _fallback_for_missing_profile():
    text = read_text(SOURCE)
    assert "except KeyError" in text or "try:" in text, "missing-profile fallback not found"
    return "missing-profile fallback present"


def _explicit_utc_present():
    text = read_text(SOURCE)
    assert "UTC" in text, "explicit UTC fallback missing"
    return "UTC fallback present"


def run():
    public = run_checks("public", [("pipeline_order_present", _pipeline_order_present)])
    hidden = run_checks(
        "hidden",
        [
            ("fallback_for_null_timezone", _fallback_for_null_timezone),
            ("fallback_for_missing_profile", _fallback_for_missing_profile),
            ("explicit_utc_present", _explicit_utc_present),
        ],
    )
    return emit_report("E2-LS1-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
