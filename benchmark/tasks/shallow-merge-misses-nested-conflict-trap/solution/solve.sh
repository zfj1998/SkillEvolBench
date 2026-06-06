#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/reconcile_nested_differences.py" <<'__SKILL_EVOL_REFERENCE_RECONCILE_NESTED_DIFFERENCES_PY_0__'
from __future__ import annotations

import json
from pathlib import Path

from deep_compare import deep_diff


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    source_a = json.loads((PROJECT_ROOT / "source_a.json").read_text(encoding="utf-8"))
    source_b = json.loads((PROJECT_ROOT / "source_b.json").read_text(encoding="utf-8"))
    right_index = {row["id"]: row for row in source_b}

    differences = []
    for left_row in source_a:
        right_row = right_index[left_row["id"]]
        for difference in deep_diff(left_row, right_row):
            entry = dict(difference)
            entry["record_id"] = left_row["id"]
            differences.append(entry)

    (PROJECT_ROOT / "reconciliation_report.json").write_text(
        json.dumps({"total_differences": len(differences), "differences": differences}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_RECONCILE_NESTED_DIFFERENCES_PY_0__

python3 "$PROJECT_ROOT/reconcile_nested_differences.py"
