from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


SOURCE = PROJECT / "client.py"


def _local_validate_exists():
    text = read_text(SOURCE)
    assert "def validate" in text, "local validate function missing"
    return "local validate exists"


def _does_not_parse_remote_400_shape():
    text = read_text(SOURCE)
    assert '["field"]' not in text and '["error"]' not in text, "code still depends on remote 400 shape"
    return "no remote 400 shape dependency"


def _error_objects_local():
    text = read_text(SOURCE)
    assert "field" not in text or "message" not in text or "validate" in text, "local error generation unclear"
    return "local error objects implied"


def run():
    public = run_checks("public", [("local_validate_exists", _local_validate_exists)])
    hidden = run_checks(
        "hidden",
        [
            ("does_not_parse_remote_400_shape", _does_not_parse_remote_400_shape),
            ("error_objects_local", _error_objects_local),
        ],
    )
    return emit_report("E2-LS1-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
