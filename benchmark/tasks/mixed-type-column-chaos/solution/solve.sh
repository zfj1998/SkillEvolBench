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
    "amount_parser.py": dedent(
        """
        from __future__ import annotations

        NULL_MARKERS = {"", "n/a", "null", "-"}


        def parse_revenue(raw: str) -> float | None:
            text = str(raw).strip()
            if text.lower() in NULL_MARKERS:
                return None
            negative = text.startswith("(") and text.endswith(")")
            if negative:
                text = text[1:-1]
            text = text.replace("$", "").replace(",", "")
            value = float(text)
            return -value if negative else value
        """
    ),
    "process_transactions.py": dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path

        import pandas as pd

        from amount_parser import parse_revenue
        from anomaly_log import build_anomaly_report

        CSV_PATH = Path("transactions.csv")
        OUTPUT_PATH = Path("output.json")


        def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
            df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)

            cleaned_values: list[float | None] = []
            parse_failures = 0
            null_rows = 0

            for raw_value in df["revenue"].tolist():
                try:
                    value = parse_revenue(raw_value)
                except ValueError:
                    parse_failures += 1
                    value = None
                if value is None:
                    text = str(raw_value).strip().lower()
                    if text in {"", "n/a", "null", "-"}:
                        null_rows += 1
                cleaned_values.append(value)

            df["revenue_clean"] = cleaned_values
            valid_df = df.dropna(subset=["revenue_clean"]).copy()
            category_totals = (
                valid_df.groupby("category")["revenue_clean"].sum().round(2).sort_index().to_dict()
            )

            payload = {
                "total_revenue": round(float(valid_df["revenue_clean"].sum()), 2),
                "valid_row_count": int(len(valid_df)),
                "dropped_row_count": int(len(df) - len(valid_df)),
                "category_totals": {key: round(float(value), 2) for key, value in category_totals.items()},
                "anomaly_report": build_anomaly_report(null_rows, parse_failures),
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
