from __future__ import annotations

import json
from pathlib import Path

from conflict_grouping import annotate_groups
from nested_diff import deep_diff


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    hr_records = json.loads((PROJECT_ROOT / "hr_records.json").read_text(encoding="utf-8"))
    finance_records = json.loads((PROJECT_ROOT / "finance_records.json").read_text(encoding="utf-8"))
    finance_index = {row["employee_id"]: row for row in finance_records}

    differences = []
    for hr_row in hr_records:
        employee_id = hr_row["employee_id"]
        for difference in deep_diff(hr_row, finance_index[employee_id]):
            enriched = dict(difference)
            enriched["employee_id"] = employee_id
            differences.append(enriched)

    differences = annotate_groups(differences)
    (PROJECT_ROOT / "differences_report.json").write_text(
        json.dumps({"total_differences": len(differences), "differences": differences}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
