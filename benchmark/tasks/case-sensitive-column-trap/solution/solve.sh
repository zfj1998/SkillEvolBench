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
    "schema_casefold.py": dedent(
        """
        from __future__ import annotations


        def resolve_metric_column(columns, desired: str = "amount") -> str:
            normalized = {str(column).strip().lower(): column for column in columns}
            actual = normalized.get(desired.lower())
            if actual is None:
                raise KeyError(f"missing metric column: {desired}")
            return actual
        """
    ),
    "process_amounts.py": dedent(
        """
        from __future__ import annotations

        import json
        import os
        from pathlib import Path

        import pandas as pd

        from schema_casefold import resolve_metric_column

        DEFAULT_SOURCE = Path("sales_data.csv")
        OUTPUT_PATH = Path("output.json")


        def run(source: Path | None = None, output_path: Path = OUTPUT_PATH) -> dict:
            csv_path = Path(os.environ.get("SALES_SOURCE", source or DEFAULT_SOURCE))
            df = pd.read_csv(csv_path)
            metric_column = resolve_metric_column(df.columns, "amount")
            total = round(float(pd.to_numeric(df[metric_column], errors="raise").sum()), 2)
            payload = {
                "metric_column": str(metric_column).strip().lower(),
                "total_amount": total,
                "row_count": int(len(df)),
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
