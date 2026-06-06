from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
POLICY = PROJECT / "null_policy.py"
MERGE = PROJECT / "merge_inventory.py"


def run():
    policy = read_text(POLICY).lower()
    merge = read_text(MERGE)
    public = run_checks("public", [
        ("uses_keep_default_na_false", lambda: "keep_default_na=False" in merge or (_ for _ in ()).throw(AssertionError("raw supplier null tokens not preserved"))),
    ])
    hidden = run_checks("hidden", [
        ("source_aware_null_policy", lambda: all(token in policy for token in ["supplier_a", "supplier_b", "supplier_c"]) or (_ for _ in ()).throw(AssertionError("policy is not source-aware"))),
        ("does_not_globally_treat_zero_as_missing", lambda: '"0"' not in policy.split("common_null_strings", 1)[-1] or "supplier_c" in policy or (_ for _ in ()).throw(AssertionError("zero still handled as a global null token"))),
        ("keeps_zero_stock_valid", lambda: 'column == "stock"' in policy and '"0"' not in policy.split('column == "stock"', 1)[-1].split("return", 1)[0] or (_ for _ in ()).throw(AssertionError("stock=0 is not preserved as valid"))),
        ("supplier_c_price_zero_invalid", lambda: 'column == "price"' in policy and '"0"' in policy.split('column == "price"', 1)[-1] or (_ for _ in ()).throw(AssertionError("supplier C price=0 rule missing"))),
    ])
    return emit_report("E3-LS4-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
