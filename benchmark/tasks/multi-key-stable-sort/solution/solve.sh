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
    "tie_break_policy.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd


        def order_employees(df: pd.DataFrame) -> pd.DataFrame:
            return df.sort_values(
                ["department", "salary", "_feed_order"],
                ascending=[True, False, True],
                kind="mergesort",
            ).reset_index(drop=True)
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
