from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
POLICY = PROJECT / "offline_policy.py"
SCRIPT = PROJECT / "compute_temperature_summary.py"
CLASSIFIER = PROJECT / "reading_classifier.py"


def run():
    policy = read_text(POLICY)
    script = read_text(SCRIPT)
    classifier = read_text(CLASSIFIER)
    public = run_checks("public", [
        ("parses_numeric_temperatures", lambda: "to_numeric" in policy or (_ for _ in ()).throw(AssertionError("temperature parsing missing"))),
    ])
    hidden = run_checks("hidden", [
        ("does_not_fill_missing_with_zero", lambda: "fillna(0)" not in policy or (_ for _ in ()).throw(AssertionError("still uses fillna(0)"))),
        ("uses_dropna_or_mean", lambda: ".dropna()" in policy or ".mean()" in policy or (_ for _ in ()).throw(AssertionError("valid-reading average strategy missing"))),
        ("does_not_reclassify_zero_as_offline", lambda: ".replace(0, pd.NA)" not in policy and "offline_mask = temperatures.isna() | (temperatures == 0)" not in classifier and "offline_mask=temperatures.isna()|(temperatures==0)" not in classifier.replace(" ", "") or (_ for _ in ()).throw(AssertionError("zero-degree readings are being treated as offline"))),
        ("reports_offline_counts", lambda: "offline_reading_count" in script and "zero_degree_count" in script or (_ for _ in ()).throw(AssertionError("offline/zero audit missing"))),
    ])
    return emit_report("E3-LS4-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
