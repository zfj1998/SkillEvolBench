from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
JOIN_SELECTOR = PROJECT / "join_selector.py"
SCRIPT = PROJECT / "merge_user_spending.py"


def run():
    join_selector = read_text(JOIN_SELECTOR)
    script = read_text(SCRIPT)
    public = run_checks("public", [
        ("explicit_user_id_join", lambda: "user_id" in join_selector or (_ for _ in ()).throw(AssertionError("transactions.user_id not selected"))),
    ])
    hidden = run_checks("hidden", [
        ("avoids_transactions_id_join", lambda: 'return "id", "id"' not in join_selector or (_ for _ in ()).throw(AssertionError("still joining on transactions.id"))),
        ("merged_row_audit_present", lambda: "merged_row_count" in script or (_ for _ in ()).throw(AssertionError("merged row audit missing"))),
    ])
    return emit_report("E3-LS3-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
