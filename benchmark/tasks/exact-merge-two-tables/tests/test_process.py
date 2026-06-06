from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
MERGE_CONTRACT = PROJECT / "merge_contract.py"
AUDIT = PROJECT / "join_audit.py"


def run():
    merge_contract = read_text(MERGE_CONTRACT)
    audit = read_text(AUDIT)
    public = run_checks("public", [
        ("uses_left_merge", lambda: 'how="left"' in merge_contract or "how='left'" in merge_contract or (_ for _ in ()).throw(AssertionError("left merge missing"))),
    ])
    hidden = run_checks("hidden", [
        ("tracks_has_orders", lambda: "has_orders" in merge_contract or (_ for _ in ()).throw(AssertionError("has_orders marker missing"))),
        ("fills_missing_numeric_values", lambda: "fillna(0" in merge_contract or (_ for _ in ()).throw(AssertionError("missing numeric fill handling"))),
        ("audit_counts_unmatched", lambda: "missing_count" in audit or (_ for _ in ()).throw(AssertionError("unmatched audit missing"))),
    ])
    return emit_report("E3-LS3-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
