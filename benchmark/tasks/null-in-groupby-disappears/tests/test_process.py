from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
NORMALIZER = PROJECT / "region_normalizer.py"
SCRIPT = PROJECT / "aggregate_regional_sales.py"


def run():
    normalizer = read_text(NORMALIZER)
    script = read_text(SCRIPT)
    public = run_checks("public", [
        ("normalizes_region_values", lambda: "REGION_ALIASES" in normalizer or (_ for _ in ()).throw(AssertionError("region alias normalization missing"))),
    ])
    hidden = run_checks("hidden", [
        ("preserves_unknown_bucket", lambda: "dropna=False" in script or "fillna(UNKNOWN_REGION)" in script or (_ for _ in ()).throw(AssertionError("NaN region bucket still gets dropped"))),
        ("tracks_unresolved_rows", lambda: "unresolved_row_count" in script or (_ for _ in ()).throw(AssertionError("unresolved-row audit missing"))),
        ("reconciles_grouped_total", lambda: "matches_source_total" in script or "build_reconciliation" in script or (_ for _ in ()).throw(AssertionError("source-vs-group reconciliation missing"))),
    ])
    return emit_report("E3-LS4-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
