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

FILES = {
    "sentinel_registry.py": dedent(
        """
        from __future__ import annotations

        from schema_cleaner import clean_text

        AGE_MISSING = {"", "n/a", "na", "null", "none", "-1", "−1"}
        SALARY_MISSING = {"", "n/a", "na", "null", "none"}
        TEMPERATURE_MISSING = {"", "n/a", "na", "null", "none", "-999", "-999.0", "−999", "sensor_fault"}


        def _to_number(value: object, *, allow_decimal: bool) -> float | None:
            cleaned = clean_text(value).replace("_", "").replace(",", ".")
            try:
                number = float(cleaned)
            except ValueError:
                return None
            if not allow_decimal and not number.is_integer():
                return None
            return number


        def clean_age(value: object) -> float | None:
            cleaned = clean_text(value).lower()
            if cleaned in AGE_MISSING:
                return None
            return _to_number(value, allow_decimal=False)


        def clean_salary(value: object) -> float | None:
            cleaned = clean_text(value).lower().replace(",", "").replace("_", "")
            if cleaned in SALARY_MISSING:
                return None
            try:
                number = float(cleaned)
            except ValueError:
                return None
            if not number.is_integer():
                return None
            return number


        def clean_temperature(value: object) -> float | None:
            cleaned = clean_text(value).lower()
            if cleaned in TEMPERATURE_MISSING:
                return None
            return _to_number(value, allow_decimal=True)
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
