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
    "reading_classifier.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd


        def classify_temperature_readings(temperatures: pd.Series) -> dict[str, int]:
            offline_mask = temperatures.isna()
            return {
                "offline_reading_count": int(offline_mask.sum()),
                "zero_degree_count": int((temperatures == 0).sum()),
            }
        """
    ),
    "offline_policy.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd

        from reading_classifier import classify_temperature_readings


        def parse_temperature_series(frame: pd.DataFrame) -> pd.Series:
            temperatures = pd.to_numeric(frame["temperature"], errors="coerce")
            classify_temperature_readings(temperatures)
            return temperatures


        def compute_average_temperature(temperatures: pd.Series) -> float:
            valid = temperatures.dropna()
            return round(float(valid.mean()), 4) if not valid.empty else 0.0
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
