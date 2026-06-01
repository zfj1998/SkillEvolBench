#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/nested_diff.py" <<'__SKILL_EVOL_REFERENCE_NESTED_DIFF_PY_0__'
from __future__ import annotations


def deep_diff(left, right, path=""):
    diffs = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            next_path = f"{path}.{key}" if path else key
            if key not in left:
                diffs.append({"path": next_path, "hr": None, "finance": right[key]})
                continue
            if key not in right:
                diffs.append({"path": next_path, "hr": left[key], "finance": None})
                continue
            diffs.extend(deep_diff(left[key], right[key], next_path))
        return diffs

    if left != right:
        return [{"path": path, "hr": left, "finance": right}]

    return []
__SKILL_EVOL_REFERENCE_NESTED_DIFF_PY_0__
cat > "$PROJECT_ROOT/build_differences_report.py" <<'__SKILL_EVOL_REFERENCE_BUILD_DIFFERENCES_REPORT_PY_0__'
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
__SKILL_EVOL_REFERENCE_BUILD_DIFFERENCES_REPORT_PY_0__

python3 "$PROJECT_ROOT/build_differences_report.py"
