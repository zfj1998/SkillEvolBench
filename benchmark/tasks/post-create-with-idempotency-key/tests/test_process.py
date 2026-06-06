from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

SOURCE = PROJECT / "order_client.py"


def _adds_idempotency_key_header():
    text = read_text(SOURCE)
    assert "Idempotency-Key" in text, "expected Idempotency-Key header"
    return "adds idempotency key"


def _uses_uuid_generation():
    text = read_text(SOURCE)
    assert "uuid.uuid4" in text, "expected UUID-based key generation"
    return "uses uuid"


def _creates_key_before_retry_loop():
    text = read_text(SOURCE)
    key_index = text.index("idempotency_key")
    loop_index = text.index("for attempt")
    assert key_index < loop_index, "key should be created once before retries"
    return "key created before retry loop"


def _keeps_retry_count_bounded():
    text = read_text(SOURCE)
    assert "max_attempts" in text, "expected bounded attempts"
    return "bounded attempts"


def run():
    public = run_checks("public", [("adds_idempotency_key_header", _adds_idempotency_key_header)])
    hidden = run_checks(
        "hidden",
        [
            ("uses_uuid_generation", _uses_uuid_generation),
            ("creates_key_before_retry_loop", _creates_key_before_retry_loop),
            ("keeps_retry_count_bounded", _keeps_retry_count_bounded),
        ],
    )
    return emit_report("E2-LS2-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
