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
    "schema_registry.py": dedent(
        """
        from __future__ import annotations

        CANONICAL_COLUMNS = ("id", "name", "amount", "date")


        def _normalize_header(raw: str) -> str:
            return str(raw).replace("\\ufeff", "").strip().lower()


        def build_column_map(columns) -> dict[str, str]:
            mapping: dict[str, str] = {}
            for column in columns:
                mapping[_normalize_header(column)] = column
            return mapping


        def require_canonical_columns(columns) -> dict[str, str]:
            mapping = build_column_map(columns)
            resolved: dict[str, str] = {}
            missing: list[str] = []
            for canonical in CANONICAL_COLUMNS:
                actual = mapping.get(canonical)
                if actual is None:
                    missing.append(canonical)
                    continue
                resolved[canonical] = actual
            if missing:
                raise KeyError(f"missing canonical columns: {missing}")
            return resolved
        """
    ),
    "process_sales.py": dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path

        import pandas as pd

        from aggregation_plan import build_summary_frame
        from schema_registry import require_canonical_columns

        CSV_PATH = Path("sales.csv")
        OUTPUT_PATH = Path("output.json")


        def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
            df = pd.read_csv(csv_path)
            raw_columns = list(df.columns)
            column_map = require_canonical_columns(df.columns)
            df = df.rename(columns={actual: canonical for canonical, actual in column_map.items()})
            df["id"] = pd.to_numeric(df["id"], errors="raise").astype(int)
            df["amount"] = pd.to_numeric(df["amount"], errors="raise")

            summary_rows = []
            for _, row in build_summary_frame(df).iterrows():
                summary_rows.append(
                    {
                        "name": row["name"],
                        "total_amount": round(float(row["sum"]), 2),
                        "average_amount": round(float(row["mean"]), 2),
                        "transaction_count": int(row["count"]),
                    }
                )

            payload = {
                "summary": summary_rows,
                "grand_total": round(float(df["amount"].sum()), 2),
                "row_count": int(len(df)),
                "schema_report": {
                    "raw_columns": raw_columns,
                    "canonical_columns": list(df.columns),
                    "id_dtype": str(df["id"].dtype),
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
