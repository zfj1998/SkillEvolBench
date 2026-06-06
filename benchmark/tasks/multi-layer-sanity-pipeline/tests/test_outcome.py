from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()
SCRIPT = PROJECT_ROOT / "build_operations_quality_report.py"
DB_PATH = PROJECT_ROOT / "operations.db"
CSV_PATH = PROJECT_ROOT / "international_offices.csv"
OUTPUT = PROJECT_ROOT / "output.json"


def expected_report() -> dict[str, object]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row_counts = {
            "monthly_revenue": conn.execute("SELECT COUNT(*) FROM monthly_revenue").fetchone()[0],
            "department_budget": conn.execute("SELECT COUNT(*) FROM department_budget").fetchone()[0],
            "projects": conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            "project_departments": conn.execute("SELECT COUNT(*) FROM project_departments").fetchone()[0],
        }
        revenue_rows = [dict(row) for row in conn.execute("SELECT month, region, revenue, batch_id FROM monthly_revenue ORDER BY month, region, batch_id").fetchall()]
        null_department_rows = conn.execute("SELECT COUNT(*) FROM department_budget WHERE department IS NULL").fetchone()[0]
        project_total = round(float(conn.execute("SELECT SUM(total_cost) FROM projects").fetchone()[0] or 0.0), 2)
        allocation_total = round(float(conn.execute("SELECT SUM(allocated_cost) FROM project_departments").fetchone()[0] or 0.0), 2)
    finally:
        conn.close()

    grouped = defaultdict(list)
    for row in revenue_rows:
        grouped[(row["month"], row["region"])].append(row)

    issues = []
    corrected_total = 0.0
    region_month_values = defaultdict(list)
    for (month, region), rows in grouped.items():
        canonical_row = sorted(rows, key=lambda row: row["batch_id"])[0]
        canonical_revenue = float(canonical_row["revenue"])
        corrected_total += canonical_revenue
        region_month_values[region].append((month, canonical_revenue, len(rows)))
        if len(rows) > 1:
            issues.append(("duplicate_region_month_batches", month, region))

    from statistics import median

    for region, rows in region_month_values.items():
        baseline = median(value for _, value, _ in rows)
        for month, revenue, batch_count in rows:
            if baseline > 0 and revenue > baseline * 3:
                issues.append(("revenue_spike", month, region))

    office_rows = list(csv.DictReader(CSV_PATH.open("r", encoding="utf-8", newline="")))
    invalid_status_rows = [row for row in office_rows if str(row.get("status", "")).strip().lower() not in {"active", "inactive"}]

    kinds = []
    if null_department_rows:
        kinds.append("null_department")
    kinds.extend(kind for kind, *_ in issues)
    if invalid_status_rows:
        kinds.append("invalid_office_status")
    if abs(project_total - allocation_total) > 0.01:
        kinds.append("allocation_mismatch")

    confidence = "high" if len(kinds) == 0 else "medium" if len(kinds) == 1 else "low"
    return {
        "row_counts": row_counts,
        "null_department_rows": null_department_rows,
        "invalid_status_rows": invalid_status_rows,
        "project_total": project_total,
        "allocation_total": allocation_total,
        "issue_kinds": kinds,
        "confidence": confidence,
        "corrected_total_revenue": round(corrected_total, 2),
    }


def run_script() -> tuple[subprocess.CompletedProcess[str], dict]:
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT_ROOT, capture_output=True, text=True)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = expected_report()

    public = run_checks(
        "public",
        [
            ("output_exists", lambda: run_script()[0].returncode == 0 and OUTPUT.exists() or (_ for _ in ()).throw(AssertionError("output missing"))),
            ("confidence_present", lambda: "confidence" in run_script()[1] or (_ for _ in ()).throw(AssertionError("confidence missing"))),
        ],
    )

    def check_issue_kinds() -> None:
        payload = run_script()[1]
        kinds = [issue["kind"] for issue in payload["issues"]]
        for expected_kind in expected["issue_kinds"]:
            assert expected_kind in kinds, f"missing issue kind {expected_kind}"
        assert len(kinds) >= 4, "expected multiple issues in quality report"

    hidden = run_checks(
        "hidden",
        [
            ("script_succeeds", lambda: run_script()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError(run_script()[0].stderr[:400]))),
            ("row_counts_match_sources", lambda: run_script()[1]["row_counts"] == expected["row_counts"] or (_ for _ in ()).throw(AssertionError("row counts mismatch"))),
            ("multiple_quality_issues_detected", check_issue_kinds),
            ("cross_query_reconciliation_is_strict", lambda: run_script()[1]["cross_query"]["projects_total"] == expected["project_total"] and run_script()[1]["cross_query"]["allocations_total"] == expected["allocation_total"] and run_script()[1]["cross_query"]["match"] is False or (_ for _ in ()).throw(AssertionError("cross-query check mismatch"))),
            ("office_status_issue_detected", lambda: len(run_script()[1]["office_registry"]["invalid_status_rows"]) == len(expected["invalid_status_rows"]) == 1 or (_ for _ in ()).throw(AssertionError("invalid office status not detected"))),
            ("confidence_and_corrected_total_use_cleaned_view", lambda: run_script()[1]["confidence"] == expected["confidence"] == "low" and run_script()[1]["corrected_total_revenue"] == expected["corrected_total_revenue"] == 4715849.18 or (_ for _ in ()).throw(AssertionError("confidence or corrected total mismatch"))),
        ],
    )
    return emit_report("E3-LS5-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
