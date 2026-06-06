from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_orders.py"
CONTRACT = PROJECT / "key_contract.py"


def run():
    script = read_text(SCRIPT)
    contract = read_text(CONTRACT)
    public = run_checks("public", [
        ("key_normalization_present", lambda: "normalize_dimension_key" in script and "normalize_fact_key" in script or (_ for _ in ()).throw(AssertionError("key normalization missing"))),
    ])
    hidden = run_checks("hidden", [
        ("prefix_alignment_logic", lambda: "USR" in contract or (_ for _ in ()).throw(AssertionError("prefixed key handling missing"))),
        ("merge_validation_present", lambda: "merged.empty" in script or "merged_row_count" in script or (_ for _ in ()).throw(AssertionError("merge validation missing"))),
        ("no_blind_empty_merge", lambda: "return {}" not in script or (_ for _ in ()).throw(AssertionError("empty merge shortcut detected"))),
    ])
    return emit_report("E3-LS1-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
