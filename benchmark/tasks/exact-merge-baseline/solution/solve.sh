#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/conflict_policy.py" <<'__SKILL_EVOL_REFERENCE_CONFLICT_POLICY_PY_0__'
from __future__ import annotations


def collect_conflicts(joined_rows: list[tuple[dict, dict]]) -> list[dict]:
    conflicts: list[dict] = []
    for employee_row, salary_row in joined_rows:
        if employee_row.get("dept") and salary_row.get("dept") and employee_row["dept"] != salary_row["dept"]:
            conflicts.append(
                {
                    "employee_id": employee_row["employee_id"],
                    "field": "dept",
                    "employees_value": employee_row["dept"],
                    "salaries_value": salary_row["dept"],
                    "resolved_to": employee_row["dept"],
                    "resolved_by": "employees.json (priority 1)",
                    "merge_key": "employee_id",
                    "source_priority": "employees.json > salaries.json",
                }
            )
    return conflicts
__SKILL_EVOL_REFERENCE_CONFLICT_POLICY_PY_0__
cat > "$PROJECT_ROOT/conflict_summary.py" <<'__SKILL_EVOL_REFERENCE_CONFLICT_SUMMARY_PY_0__'
from __future__ import annotations


def build_summary(conflicts: list[dict]) -> dict:
    field_counts: dict[str, int] = {}
    for conflict in conflicts:
        field = conflict.get("field", "")
        field_counts[field] = field_counts.get(field, 0) + 1
    return {
        "review_queue_size": len(conflicts),
        "field_counts": field_counts,
    }
__SKILL_EVOL_REFERENCE_CONFLICT_SUMMARY_PY_0__
cat > "$PROJECT_ROOT/merge_employee_records.py" <<'__SKILL_EVOL_REFERENCE_MERGE_EMPLOYEE_RECORDS_PY_0__'
from __future__ import annotations

import csv
import json
from pathlib import Path

from conflict_policy import collect_conflicts
from conflict_summary import build_summary
from exact_join import join_exact


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    employees = json.loads((PROJECT_ROOT / "employees.json").read_text(encoding="utf-8"))
    salaries = json.loads((PROJECT_ROOT / "salaries.json").read_text(encoding="utf-8"))

    joined = join_exact(employees, salaries)
    conflicts = collect_conflicts(joined)

    master = []
    for employee_row, salary_row in joined:
        master.append(
            {
                "employee_id": employee_row["employee_id"],
                "name": employee_row["name"],
                "dept": employee_row["dept"],
                "manager": employee_row["manager"],
                "location": employee_row["location"],
                "salary": salary_row.get("salary", ""),
                "grade": salary_row.get("grade", ""),
                "start_date": salary_row.get("start_date", ""),
            }
        )

    with (PROJECT_ROOT / "master_employees.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["employee_id", "name", "dept", "manager", "location", "salary", "grade", "start_date"],
        )
        writer.writeheader()
        writer.writerows(master)

    (PROJECT_ROOT / "conflict_log.json").write_text(
        json.dumps(
            {
                "merge_key": "employee_id",
                "source_priority": "employees.json > salaries.json",
                "total_conflicts": len(conflicts),
                "summary": build_summary(conflicts),
                "conflicts": conflicts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_MERGE_EMPLOYEE_RECORDS_PY_0__

python3 "$PROJECT_ROOT/merge_employee_records.py"
