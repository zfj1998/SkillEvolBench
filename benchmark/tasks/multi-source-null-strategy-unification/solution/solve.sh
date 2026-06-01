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
    "null_policy.py": dedent(
        """
        from __future__ import annotations

        import math

        import numpy as np
        import pandas as pd

        COMMON_NULL_STRINGS = {"", "na", "n/a", "null", "none"}


        def _normalize_text(value: object) -> str:
            return str(value).strip().lower()


        def standardize_value(source: str, column: str, value: object):
            if value is None:
                return np.nan
            if isinstance(value, float) and not math.isfinite(value):
                return np.nan

            text = str(value).strip()
            lower = _normalize_text(value)

            if source == "supplier_a":
                if text == "":
                    return np.nan
                return text

            if source == "supplier_b":
                if lower in COMMON_NULL_STRINGS:
                    return np.nan
                return text

            if source == "supplier_c":
                if column == "price":
                    if lower in {"-1", "-1.0", "-999", "-999.0", "0", "0.0"}:
                        return np.nan
                    return text
                if column == "stock":
                    if lower in {"-1", "-1.0", "-999", "-999.0"}:
                        return np.nan
                    return text

            if lower in COMMON_NULL_STRINGS:
                return np.nan
            return text


        def to_numeric(series: pd.Series) -> pd.Series:
            return pd.to_numeric(series, errors="coerce")
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
