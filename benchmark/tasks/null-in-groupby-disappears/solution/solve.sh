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
    "aggregate_regional_sales.py": dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path

        import pandas as pd

        from aggregation_audit import build_reconciliation
        from region_normalizer import UNKNOWN_REGION, normalize_region

        INPUT_PATH = Path("regional_sales.csv")
        OUTPUT_PATH = Path("output.json")


        def run(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> dict:
            frame = pd.read_csv(input_path)
            frame["amount"] = pd.to_numeric(frame["amount"].astype(str).str.replace(",", "", regex=False), errors="coerce")
            frame["normalized_region"] = frame["region"].map(normalize_region).fillna(UNKNOWN_REGION)
            grouped = (
                frame.groupby("normalized_region", dropna=False, as_index=False)["amount"]
                .sum()
                .rename(columns={"normalized_region": "region", "amount": "total_amount"})
                .sort_values("region", kind="mergesort")
            )
            source_total = float(frame["amount"].sum())
            grouped_total = float(grouped["total_amount"].sum())
            payload = {
                "records": grouped.to_dict(orient="records"),
                "source_total": round(source_total, 2),
                "grouped_total": round(grouped_total, 2),
                "unresolved_row_count": int((frame["normalized_region"] == UNKNOWN_REGION).sum()),
                "reconciliation": build_reconciliation(source_total, grouped_total),
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
