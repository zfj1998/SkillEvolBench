from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
POLICY = PROJECT / "tie_break_policy.py"
CONTRACT = PROJECT / "sort_contract.py"


def run():
    policy = read_text(POLICY)
    contract = read_text(CONTRACT)
    public = run_checks("public", [
        ("feed_order_attached", lambda: "_feed_order" in contract or (_ for _ in ()).throw(AssertionError("feed order tracking missing"))),
    ])
    hidden = run_checks("hidden", [
        ("stable_sort_present", lambda: "mergesort" in policy or (_ for _ in ()).throw(AssertionError("stable sort kind missing"))),
        ("uses_feed_order_for_ties", lambda: "_feed_order" in policy or (_ for _ in ()).throw(AssertionError("tie handling does not preserve original order"))),
        ("no_hire_date_tiebreak", lambda: "\"hire_date\"" not in policy and "'hire_date'" not in policy or (_ for _ in ()).throw(AssertionError("business tiebreaker still present"))),
    ])
    return emit_report("E3-LS2-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
