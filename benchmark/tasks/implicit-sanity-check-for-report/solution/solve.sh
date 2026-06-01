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


calendar_guard = PROJECT_ROOT / "calendar_guard.py"
replace_once(calendar_guard, "from sales_cleaning import normalize_date\n\n\n", "")
replace_once(
    calendar_guard,
    dedent(
        '''\
        def observed_days_from_raw(rows: list[dict[str, object]]) -> list[str]:
            return sorted({normalize_date(row["date"]) for row in rows if normalize_date(row["date"])})


        def missing_days(rows: list[dict[str, object]]) -> list[str]:
            observed = set(observed_days_from_raw(rows))
            return [day for day in expected_march_days() if day not in observed]
        '''
    ),
    dedent(
        '''\
        def observed_days_from_valid_rows(valid_rows: list[dict[str, object]]) -> list[str]:
            return sorted({str(row["date"]) for row in valid_rows})


        def missing_days(valid_rows: list[dict[str, object]]) -> list[str]:
            observed = set(observed_days_from_valid_rows(valid_rows))
            return [day for day in expected_march_days() if day not in observed]
        '''
    ),
)

report_annotations = PROJECT_ROOT / "report_annotations.py"
report_annotations.write_text(
    dedent(
        '''\
        from __future__ import annotations


        def build_quality_note(missing_days: list[str]) -> tuple[str, str]:
            if not missing_days:
                return "complete", "March data coverage looks complete."
            return "incomplete", f"{len(missing_days)} days are missing from the source export: {', '.join(missing_days)}."
        '''
    ),
    encoding="utf-8",
)

build_report = PROJECT_ROOT / "build_march_sales_report.py"
replace_once(
    build_report,
    "    for row in deduped.values():\n",
    "    valid_rows = list(deduped.values())\n    for row in valid_rows:\n",
)
replace_once(build_report, "    missing = missing_days(rows)\n", "    missing = missing_days(valid_rows)\n")
__SKILL_EVOL_SOLVE_PY_0__
