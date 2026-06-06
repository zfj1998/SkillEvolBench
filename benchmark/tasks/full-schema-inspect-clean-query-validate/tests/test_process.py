from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_pipeline.py"
INSPECTOR = PROJECT / "schema_inspector.py"
CLEANER = PROJECT / "amount_cleaner.py"
VALIDATOR = PROJECT / "totals_validator.py"


def run():
    script = read_text(SCRIPT)
    inspector = read_text(INSPECTOR)
    cleaner = read_text(CLEANER)
    validator = read_text(VALIDATOR)
    public = run_checks("public", [
        ("schema_inspection_present", lambda: "apply_canonical_headers" in script or (_ for _ in ()).throw(AssertionError("schema inspection missing"))),
    ])
    hidden = run_checks("hidden", [
        ("amount_cleanup_handles_parentheses", lambda: "negative_mask" in cleaner or "startswith(\"(\")" in cleaner or (_ for _ in ()).throw(AssertionError("accounting-format cleanup missing"))),
        ("zwsp_cleanup_present", lambda: "\\u200b" in cleaner or (_ for _ in ()).throw(AssertionError("ZWSP cleanup missing"))),
        ("validation_against_expected_present", lambda: "build_validation_report" in script and "expected_totals.json" in script or (_ for _ in ()).throw(AssertionError("expected-total validation missing"))),
        ("strict_threshold_present", lambda: "<= 1.0" in validator or (_ for _ in ()).throw(AssertionError("strict validation threshold missing"))),
        ("header_normalization_present", lambda: ".strip().lower()" in inspector or (_ for _ in ()).throw(AssertionError("header normalization missing"))),
    ])
    return emit_report("E3-LS1-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
