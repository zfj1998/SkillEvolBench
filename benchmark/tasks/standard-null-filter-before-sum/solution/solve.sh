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
    "denominator_policy.py": dedent(
        """
        from __future__ import annotations


        def select_denominator(total_rows: int, valid_amount_count: int, missing_amount_count: int) -> dict:
            return {
                "denominator_used": int(valid_amount_count),
                "denominator_strategy": "valid_amount_rows",
                "missing_rows_seen": int(missing_amount_count),
            }
        """
    ),
    "amount_contract.py": dedent(
        """
        from __future__ import annotations

        from pathlib import Path

        import pandas as pd

        from denominator_policy import select_denominator


        def load_orders(path: Path) -> pd.DataFrame:
            frame = pd.read_csv(path)
            frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
            return frame


        def compute_amount_summary(frame: pd.DataFrame) -> dict:
            valid_amounts = frame["amount"].dropna()
            total_amount = float(valid_amounts.sum())
            valid_amount_count = int(valid_amounts.shape[0])
            missing_amount_count = int(frame["amount"].isna().sum())
            denominator = select_denominator(
                total_rows=int(len(frame)),
                valid_amount_count=valid_amount_count,
                missing_amount_count=missing_amount_count,
            )
            average_amount = round(float(valid_amounts.mean()), 4) if valid_amount_count else 0.0
            return {
                "average_amount": average_amount,
                "total_rows": int(len(frame)),
                "valid_amount_count": valid_amount_count,
                "missing_amount_count": missing_amount_count,
                "total_amount": round(total_amount, 4),
                "denominator_used": int(denominator["denominator_used"]),
                "denominator_strategy": denominator["denominator_strategy"],
            }
        """
    ),
    "sanity_audit.py": dedent(
        """
        from __future__ import annotations


        def build_sanity_checks(summary: dict) -> dict:
            total_rows = int(summary["total_rows"])
            valid_count = int(summary["valid_amount_count"])
            missing_count = int(summary["missing_amount_count"])
            average_amount = float(summary["average_amount"])
            denominator_used = int(summary.get("denominator_used", total_rows))
            return {
                "non_empty_valid_values": valid_count > 0,
                "count_consistent": valid_count + missing_count == total_rows,
                "denominator_matches_valid_rows": denominator_used == valid_count,
                "average_in_expected_band": 90.0 <= average_amount <= 110.0,
            }
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
