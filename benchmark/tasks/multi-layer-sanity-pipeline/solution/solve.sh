#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected snippet not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    PROJECT_ROOT / "revenue_anomaly.py",
    dedent(
        '''\
        def detect_revenue_anomalies(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], float]:
            by_region = defaultdict(list)
            total_revenue = 0.0
            for row in rows:
                revenue = float(row["revenue"])
                by_region[str(row["region"])].append((str(row["month"]), revenue, str(row["batch_id"])))
                total_revenue += revenue

            anomalies = []
            for region, values in by_region.items():
                baseline = median(revenue for _, revenue, _ in values)
                for month, revenue, batch_id in values:
                    if baseline > 0 and revenue > baseline * 3:
                        anomalies.append(
                            {
                                "kind": "revenue_spike",
                                "source": "monthly_revenue",
                                "detail": f"{month} {region} revenue {revenue:.2f} exceeds baseline {baseline:.2f}",
                                "impact": "medium",
                                "month": month,
                                "region": region,
                                "batch_id": batch_id,
                            }
                        )
            return anomalies, round(total_revenue, 2)
        '''
    ),
    dedent(
        '''\
        def detect_revenue_anomalies(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], float]:
            grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
            for row in rows:
                grouped[(str(row["month"]), str(row["region"]))].append(row)

            by_region_month = defaultdict(list)
            corrected_total = 0.0
            anomalies = []

            for (month, region), group_rows in grouped.items():
                canonical_row = sorted(group_rows, key=lambda row: str(row["batch_id"]))[0]
                canonical_revenue = float(canonical_row["revenue"])
                corrected_total += canonical_revenue
                by_region_month[region].append((month, canonical_revenue, len(group_rows)))

                if len(group_rows) > 1:
                    duplicate_batches = [str(row["batch_id"]) for row in sorted(group_rows, key=lambda row: str(row["batch_id"]))[1:]]
                    anomalies.append(
                        {
                            "kind": "duplicate_region_month_batches",
                            "source": "monthly_revenue",
                            "detail": f"{month} {region} has {len(group_rows)} batches for one reporting bucket",
                            "impact": "high",
                            "month": month,
                            "region": region,
                            "duplicate_batches": duplicate_batches,
                        }
                    )

            for region, monthly_values in by_region_month.items():
                baseline = median(value for _, value, _ in monthly_values)
                for month, revenue, batch_count in monthly_values:
                    if baseline > 0 and revenue > baseline * 3:
                        anomalies.append(
                            {
                                "kind": "revenue_spike",
                                "source": "monthly_revenue",
                                "detail": f"{month} {region} revenue {revenue:.2f} exceeds baseline {baseline:.2f}",
                                "impact": "medium",
                                "month": month,
                                "region": region,
                                "batch_count": batch_count,
                            }
                        )
            return anomalies, round(corrected_total, 2)
        '''
    ),
)

replace_once(PROJECT_ROOT / "consistency_guard.py", "<= 0.1", "<= 0.01")

replace_once(
    PROJECT_ROOT / "office_registry.py",
    dedent(
        '''\
        def inspect_offices(csv_path: Path) -> dict[str, object]:
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            return {
                "row_count": len(rows),
                "invalid_status_rows": [],
                "rows": rows,
            }
        '''
    ),
    dedent(
        '''\
        VALID_STATUSES = {"active", "inactive"}


        def inspect_offices(csv_path: Path) -> dict[str, object]:
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            invalid_status_rows = []
            for row in rows:
                status = str(row.get("status", "")).strip().lower()
                if status not in VALID_STATUSES:
                    invalid_status_rows.append(
                        {
                            "office_id": row.get("office_id"),
                            "city": row.get("city"),
                            "status": row.get("status"),
                        }
                    )
            return {
                "row_count": len(rows),
                "invalid_status_rows": invalid_status_rows,
                "rows": rows,
            }
        '''
    ),
)

replace_once(
    PROJECT_ROOT / "confidence_policy.py",
    dedent(
        '''\
        def classify_confidence(issue_count: int) -> str:
            if issue_count == 0:
                return "high"
            return "medium"
        '''
    ),
    dedent(
        '''\
        def classify_confidence(issue_count: int) -> str:
            if issue_count == 0:
                return "high"
            if issue_count == 1:
                return "medium"
            return "low"
        '''
    ),
)

build_report = PROJECT_ROOT / "build_operations_quality_report.py"
build_report.write_text(
    dedent(
        '''\
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
            if office_summary["invalid_status_rows"]:
                issues.append(
                    {
                        "kind": "invalid_office_status",
                        "source": "international_offices.csv",
                        "detail": f"{len(office_summary['invalid_status_rows'])} office rows use unsupported status values",
                        "impact": "low",
                    }
                )

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
                        "detail": "Project totals do not reconcile to departmental allocations to the cent.",
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
        '''
    ),
    encoding="utf-8",
)
__SKILL_EVOL_SOLVE_PY_0__
