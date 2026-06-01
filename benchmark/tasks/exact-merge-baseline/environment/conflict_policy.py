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
                    "resolved_by": "employees.json",
                }
            )

    # Legacy audit trimming: keep only the first 12 review items.
    return conflicts[:12]
