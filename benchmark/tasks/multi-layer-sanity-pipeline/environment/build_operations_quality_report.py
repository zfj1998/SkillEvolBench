from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from confidence_policy import classify_confidence
from consistency_guard import allocation_consistent
from office_registry import inspect_offices
from revenue_anomaly import detect_revenue_anomalies
from rowcount_guard import summarize_row_counts

DB_PATH = Path("operations.db")
CSV_PATH = Path("international_offices.csv")
OUTPUT_PATH = Path("output.json")


def main() -> None:
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
        project_total = float(conn.execute("SELECT SUM(total_cost) FROM projects").fetchone()[0] or 0.0)
        allocation_total = float(conn.execute("SELECT SUM(allocated_cost) FROM project_departments").fetchone()[0] or 0.0)
    finally:
        conn.close()

    issues = summarize_row_counts(row_counts)
    if null_department_rows:
        issues.append(
            {
                "kind": "null_department",
                "source": "department_budget",
                "detail": f"{null_department_rows} budget rows have NULL department",
                "impact": "medium",
            }
        )

    revenue_issues, corrected_total_revenue = detect_revenue_anomalies(revenue_rows)
    issues.extend(revenue_issues)

    office_summary = inspect_offices(CSV_PATH)
    cross_query = {
        "projects_total": round(project_total, 2),
        "allocations_total": round(allocation_total, 2),
        "match": allocation_consistent(project_total, allocation_total),
    }
    if not cross_query["match"]:
        issues.append(
            {
                "kind": "allocation_mismatch",
                "source": "projects_vs_project_departments",
                "detail": "Project totals do not reconcile to departmental allocations",
                "impact": "high",
            }
        )

    output = {
        "row_counts": row_counts,
        "issues": issues,
        "cross_query": cross_query,
        "office_registry": office_summary,
        "confidence": classify_confidence(len(issues)),
        "corrected_total_revenue": corrected_total_revenue,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
