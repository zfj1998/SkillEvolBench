from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
CONTRACT = PROJECT / "amount_contract.py"
AUDIT = PROJECT / "sanity_audit.py"
POLICY = PROJECT / "denominator_policy.py"


def run():
    contract = read_text(CONTRACT)
    audit = read_text(AUDIT)
    policy = read_text(POLICY)
    public = run_checks("public", [
        ("parses_amount_column", lambda: "to_numeric" in contract or (_ for _ in ()).throw(AssertionError("amount parsing missing"))),
    ])
    hidden = run_checks("hidden", [
        ("uses_mean_or_valid_denominator", lambda: ".mean(" in contract or "valid_amount_count" in contract or (_ for _ in ()).throw(AssertionError("valid-value denominator logic missing"))),
        ("avoids_total_row_denominator", lambda: "total_amount / total_rows" not in contract or (_ for _ in ()).throw(AssertionError("still dividing by total rows"))),
        ("uses_explicit_denominator_policy", lambda: "select_denominator" in contract and "valid_amount_rows" in policy or (_ for _ in ()).throw(AssertionError("explicit denominator policy missing"))),
        ("reports_missing_amounts", lambda: "missing_amount_count" in contract and "count_consistent" in audit or (_ for _ in ()).throw(AssertionError("missing-value audit missing"))),
    ])
    return emit_report("E3-LS4-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
