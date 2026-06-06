from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

SOURCE = PROJECT / "pipeline_client.py"


def _has_step_local_retry_helper():
    text = read_text(SOURCE)
    assert "def fetch_details_with_retry" in text, "expected a step-local retry helper"
    return "has step-local helper"


def _auth_stays_outside_retry_helper():
    text = read_text(SOURCE)
    assert text.index("token = api.authenticate()") < text.index("details = fetch_details_with_retry("), "auth should happen before step-local retry helper"
    return "auth outside retry helper"


def _list_stays_outside_retry_helper():
    text = read_text(SOURCE)
    assert text.index("record_ids = api.list_records(token)") < text.index("details = fetch_details_with_retry("), "list should happen before step-local retry helper"
    return "list outside retry helper"


def run():
    public = run_checks("public", [("has_step_local_retry_helper", _has_step_local_retry_helper)])
    hidden = run_checks(
        "hidden",
        [
            ("auth_stays_outside_retry_helper", _auth_stays_outside_retry_helper),
            ("list_stays_outside_retry_helper", _list_stays_outside_retry_helper),
        ],
    )
    return emit_report("E2-LS2-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
