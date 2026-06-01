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
    "merge_contract.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd


        def merge_customer_orders(customers: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
            merged = customers.merge(orders, on="customer_id", how="left", validate="1:1")
            merged["has_orders"] = merged["total_orders"].notna()
            merged["total_orders"] = merged["total_orders"].fillna(0).astype(int)
            merged["total_amount"] = merged["total_amount"].fillna(0.0).round(2)
            merged["last_order_date"] = merged["last_order_date"].fillna("")
            return merged
        """
    ),
    "join_audit.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd


        def summarize_unmatched_customers(merged: pd.DataFrame) -> dict:
            missing_mask = ~merged["has_orders"]
            return {
                "missing_count": int(missing_mask.sum()),
                "missing_customer_ids": merged.loc[missing_mask, "customer_id"].astype(int).tolist()[:10],
            }
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
