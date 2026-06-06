from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

SOURCE = PROJECT / "auth_client.py"


def _distinguishes_401_and_503():
    text = read_text(SOURCE)
    assert "401" in text and "503" in text, "expected separate handling for 401 and 503"
    return "distinguishes 401 and 503"


def _has_refresh_logic():
    text = read_text(SOURCE)
    assert text.count("issue_token(") >= 2 or "refresh_token(" in text, "expected refresh token logic"
    return "has refresh logic"


def _checks_token_expired_reason():
    text = read_text(SOURCE)
    assert "token_expired" in text, "expected token_expired handling"
    return "checks token_expired"


def _keeps_retry_bound():
    text = read_text(SOURCE)
    assert "max_retries" in text, "expected bounded retries"
    return "bounded retries"


def run():
    public = run_checks("public", [("distinguishes_401_and_503", _distinguishes_401_and_503)])
    hidden = run_checks(
        "hidden",
        [
            ("has_refresh_logic", _has_refresh_logic),
            ("checks_token_expired_reason", _checks_token_expired_reason),
            ("keeps_retry_bound", _keeps_retry_bound),
        ],
    )
    return emit_report("E2-LS2-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
