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
    "key_contract.py": dedent(
        """
        from __future__ import annotations


        def normalize_dimension_key(series):
            return series.astype(int).map(lambda value: f"USR{value:03d}")


        def normalize_fact_key(series):
            return series.astype(str).str.strip().str.upper()
        """
    ),
    "process_orders.py": dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path

        import pandas as pd

        from join_plan import build_region_totals, merge_orders
        from key_contract import normalize_dimension_key, normalize_fact_key

        USERS_PATH = Path("users.csv")
        ORDERS_PATH = Path("orders.csv")
        OUTPUT_PATH = Path("output.json")


        def run(
            users_path: Path = USERS_PATH,
            orders_path: Path = ORDERS_PATH,
            output_path: Path = OUTPUT_PATH,
        ) -> dict:
            users = pd.read_csv(users_path)
            orders = pd.read_csv(orders_path)

            key_report = {
                "users_dtype_before": str(users["user_id"].dtype),
                "orders_dtype_before": str(orders["user_id"].dtype),
            }

            users["user_id"] = normalize_dimension_key(users["user_id"])
            orders["user_id"] = normalize_fact_key(orders["user_id"])

            key_report["users_dtype_after"] = str(users["user_id"].dtype)
            key_report["orders_dtype_after"] = str(orders["user_id"].dtype)

            merged = merge_orders(users, orders)
            if merged.empty:
                raise ValueError("merge produced no rows after key normalization")

            payload = {
                "region_totals": {key: round(float(value), 2) for key, value in build_region_totals(merged).items()},
                "merged_row_count": int(len(merged)),
                "merge_report": {
                    **key_report,
                    "unmatched_orders": int(len(orders) - len(merged)),
                },
            }
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload


        if __name__ == "__main__":
            run()
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
