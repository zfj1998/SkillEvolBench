from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"


def run():
    rules = read_text(PROJECT / "pricing_rules.py")
    public = run_checks("public", [
        ("checks_price_semantics", lambda: ("price < 0" in rules or "price <= 0" in rules) or (_ for _ in ()).throw(AssertionError("no semantic price check found"))),
    ])
    hidden = run_checks("hidden", [
        ("does_not_abs_negative_price", lambda: "abs(price)" not in rules or (_ for _ in ()).throw(AssertionError("negative prices are still normalized with abs()"))),
        ("keeps_zero_price_valid", lambda: "price < 0" in rules and "price <= 0" not in rules or (_ for _ in ()).throw(AssertionError("zero-price products incorrectly filtered"))),
        ("filters_invalid_records", lambda: "return False" in rules or (_ for _ in ()).throw(AssertionError("invalid records are not filtered"))),
    ])
    return emit_report("E2-LS5-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
