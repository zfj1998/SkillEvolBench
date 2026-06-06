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


def _has_exponential_term():
    text = read_text(SOURCE)
    assert "2 **" in text or "** attempt" in text or "pow(2" in text, "expected exponential backoff"
    return "contains exponential backoff"


def _has_jitter_source():
    text = read_text(SOURCE)
    assert ".uniform(" in text or "random(" in text, "expected jitter source"
    return "contains jitter"


def _has_retry_cap():
    text = read_text(SOURCE)
    assert "max_retries" in text, "expected retry cap"
    return "has retry cap"


def run():
    public = run_checks("public", [("has_exponential_term", _has_exponential_term)])
    hidden = run_checks(
        "hidden",
        [
            ("has_jitter_source", _has_jitter_source),
            ("has_retry_cap", _has_retry_cap),
        ],
    )
    return emit_report("E2-LS2-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
