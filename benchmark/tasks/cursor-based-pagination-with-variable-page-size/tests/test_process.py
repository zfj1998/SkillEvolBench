from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

SOURCE = PROJECT / "solution.py"
CONTRACT = PROJECT / "cursor_contract.py"
CHECKPOINT = PROJECT / "cursor_checkpoint.py"


def _source():
    return read_text(SOURCE)


def _uses_next_cursor():
    text = _source()
    assert "next_cursor" in text, "expected next_cursor-based pagination"
    return "next_cursor referenced"


def _terminates_on_null_cursor():
    text = _source().replace(" ", "")
    assert "isNone" in text or "==None" in text or "None:" in text, "expected explicit null-cursor termination"
    return "null cursor termination found"


def _no_offset_assumption():
    text = _source()
    assert "offset" not in text and "limit" not in text, "solution should avoid offset/limit assumptions"
    return "no offset assumptions"


def _no_fixed_limit_hint():
    text = read_text(CONTRACT)
    assert '"limit"' not in text and "'limit'" not in text, "cursor contract should not inject a fixed page-size hint"
    return "no fixed page-size hint"


def _cursor_tokens_remain_opaque():
    text = read_text(CHECKPOINT)
    assert ".split(" not in text and ".partition(" not in text and ".rsplit(" not in text, "cursor tokens should be replayed opaquely without normalization"
    return "opaque cursor handling found"


def run():
    public = run_checks("public", [("uses_next_cursor", _uses_next_cursor)])
    hidden = run_checks(
        "hidden",
        [
            ("terminates_on_null_cursor", _terminates_on_null_cursor),
            ("no_offset_assumption", _no_offset_assumption),
            ("no_fixed_limit_hint", _no_fixed_limit_hint),
            ("cursor_tokens_remain_opaque", _cursor_tokens_remain_opaque),
        ],
    )
    return emit_report("E2-LS3-T2", public, hidden)


def test_t2_process_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
