from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

SOURCE = PROJECT / "retry_client.py"


def _reads_retry_after_header():
    text = read_text(SOURCE)
    assert "Retry-After" in text, "expected Retry-After header handling"
    return "reads Retry-After"


def _waits_between_attempts():
    text = read_text(SOURCE)
    assert "sleep(" in text, "expected a wait call between retries"
    return "contains wait logic"


def _has_retry_cap():
    text = read_text(SOURCE)
    assert "max_retries" in text, "expected bounded retry count"
    return "has retry cap"


def run():
    public = run_checks("public", [("reads_retry_after_header", _reads_retry_after_header)])
    hidden = run_checks(
        "hidden",
        [
            ("waits_between_attempts", _waits_between_attempts),
            ("has_retry_cap", _has_retry_cap),
        ],
    )
    return emit_report("E2-LS2-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
