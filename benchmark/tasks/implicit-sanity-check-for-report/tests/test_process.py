from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()


def run():
    guard = read_text(PROJECT_ROOT / "calendar_guard.py")
    annotations = read_text(PROJECT_ROOT / "report_annotations.py")

    hidden = run_checks(
        "hidden",
        [
            ("calendar_guard_uses_valid_rows", lambda: "observed_days_from_valid_rows" in guard and "observed_days_from_raw" not in guard or (_ for _ in ()).throw(AssertionError("calendar guard still relies on raw row presence"))),
            ("missing_days_derived_from_valid_rows", lambda: "missing_days(valid_rows" in read_text(PROJECT_ROOT / "build_march_sales_report.py") or (_ for _ in ()).throw(AssertionError("build script not using valid-row completeness"))),
            ("annotations_mark_any_gap_incomplete", lambda: '"incomplete"' in annotations and "complete_enough" not in annotations or (_ for _ in ()).throw(AssertionError("annotations still downgrade missing days"))),
        ],
    )
    return emit_report("E3-LS5-T4", {"section": "public", "results": [], "passed": 0, "total": 0}, hidden)


if __name__ == "__main__":
    print_report(run())
