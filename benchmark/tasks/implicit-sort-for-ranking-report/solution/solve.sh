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
    "leaderboard_policy.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd


        def build_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
            totals = (
                df.groupby("salesperson", as_index=False)["amount"]
                .sum()
                .rename(columns={"amount": "total_sales"})
            )
            cutoff = totals["total_sales"].nlargest(10).iloc[-1]
            ranked = totals[totals["total_sales"] >= cutoff].copy()
            return ranked.sort_values(["total_sales", "salesperson"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
