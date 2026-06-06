from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
GUARD = PROJECT / "conversion_guard.py"
SCRIPT = PROJECT / "build_conversion_report.py"


def run():
    guard = read_text(GUARD)
    script = read_text(SCRIPT)
    public = run_checks("public", [
        ("normalizes_channels", lambda: "normalize_channel" in script or (_ for _ in ()).throw(AssertionError("channel normalization missing"))),
    ])
    hidden = run_checks("hidden", [
        ("does_not_fill_missing_denominator_with_zero", lambda: "fillna(0)" not in guard and "fillna(0)" not in script or (_ for _ in ()).throw(AssertionError("still fills denominator with zero"))),
        ("checks_impressions_before_division", lambda: "impressions is None" in guard and "== 0" in guard or (_ for _ in ()).throw(AssertionError("missing denominator guard"))),
        ("uses_missing_impression_audit", lambda: "missing_impression_rows" in script and "invalid_impression_rows" in script or (_ for _ in ()).throw(AssertionError("missing denominator audit not tracked"))),
    ])
    return emit_report("E3-LS4-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
