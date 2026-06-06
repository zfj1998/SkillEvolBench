from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


SOURCE = PROJECT / "search_client.py"


def _utc_normalization_present():
    text = read_text(SOURCE)
    assert "astimezone" in text or "timezone.utc" in text or "ZoneInfo" in text or "dateutil" in text, "UTC normalization not found"
    return "utc normalization detected"


def _explicit_timezone_policy():
    text = read_text(SOURCE)
    assert "default_timezone" in text or "if start.tzinfo is None" in text or "if end.tzinfo is None" in text, "missing explicit timezone policy"
    return "timezone policy present"


def _normalized_comparison():
    text = read_text(SOURCE)
    assert "start_utc" in text or "end_utc" in text or "normalized" in text, "normalized comparison variables not found"
    return "normalized comparison variables present"


def run():
    public = run_checks("public", [("utc_normalization_present", _utc_normalization_present)])
    hidden = run_checks(
        "hidden",
        [
            ("explicit_timezone_policy", _explicit_timezone_policy),
            ("normalized_comparison", _normalized_comparison),
        ],
    )
    return emit_report("E2-LS1-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
