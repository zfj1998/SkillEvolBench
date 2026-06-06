from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()


def run():
    views = read_text(PROJECT_ROOT / "revenue_views.py")
    guard = read_text(PROJECT_ROOT / "consistency_guard.py")
    script = read_text(PROJECT_ROOT / "reconcile_revenue_views.py")

    public = run_checks(
        "public",
        [
            ("has_two_report_views", lambda: "overall_revenue_rows" in views and "normalized_product_line_totals" in views or (_ for _ in ()).throw(AssertionError("expected report views missing"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("uses_item_amount_for_product_lines", lambda: "item_amount" in views and "SUM(CAST(o.total_amount AS REAL))" not in views or (_ for _ in ()).throw(AssertionError("product-line view still sums order totals after join"))),
            ("consistency_guard_requires_exact_match", lambda: "<= 0.01" in guard and "0.25" not in guard or (_ for _ in ()).throw(AssertionError("consistency guard still too lax"))),
            ("script_reports_cleared_difference", lambda: "\"difference\": difference" in script and "\"match\": totals_consistent" in script or (_ for _ in ()).throw(AssertionError("script missing reconciliation output"))),
        ],
    )
    return emit_report("E3-LS5-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
