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
    "amount_cleaner.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd

        NULL_MARKERS = {"", "n/a", "null", "-"}


        def clean_amount_series(series: pd.Series) -> pd.Series:
            normalized = (
                series.astype(str)
                .str.replace("\\u200b", "", regex=False)
                .str.strip()
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
            )
            negative_mask = normalized.str.startswith("(") & normalized.str.endswith(")")
            normalized = normalized.where(~negative_mask, normalized.str[1:-1])
            normalized = normalized.where(~normalized.str.lower().isin(NULL_MARKERS), other=None)
            numeric = pd.to_numeric(normalized, errors="coerce")
            numeric = numeric.where(~negative_mask, -numeric.abs())
            return numeric
        """
    ),
    "totals_validator.py": dedent(
        """
        from __future__ import annotations


        def build_validation_report(region_totals: dict[str, float], expected_totals: dict[str, float]) -> list[dict]:
            report = []
            for region, expected in sorted(expected_totals.items()):
                actual = round(float(region_totals.get(region, 0.0)), 2)
                delta = round(actual - expected, 2)
                delta_pct = abs(delta) / expected * 100 if expected else 0.0
                report.append(
                    {
                        "region": region,
                        "actual_total": actual,
                        "expected_total": expected,
                        "delta": delta,
                        "passed": delta_pct <= 1.0,
                    }
                )
            return report
        """
    ),
    "process_pipeline.py": dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path

        import pandas as pd

        from amount_cleaner import clean_amount_series
        from schema_inspector import apply_canonical_headers
        from totals_validator import build_validation_report

        CSV_PATH = Path("dirty_data.csv")
        EXPECTED_PATH = Path("expected_totals.json")
        OUTPUT_PATH = Path("output.json")


        def run(
            csv_path: Path = CSV_PATH,
            expected_path: Path = EXPECTED_PATH,
            output_path: Path = OUTPUT_PATH,
        ) -> dict:
            df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str)
            df = apply_canonical_headers(df)
            df["amount_clean"] = clean_amount_series(df["amount"])
            cleaned = df.dropna(subset=["amount_clean"]).copy()

            region_totals = cleaned.groupby("region")["amount_clean"].sum().round(2).sort_index().to_dict()
            expected_totals = json.loads(expected_path.read_text(encoding="utf-8"))
            validation_report = build_validation_report(region_totals, expected_totals)

            payload = {
                "region_totals": {key: round(float(value), 2) for key, value in region_totals.items()},
                "validation_report": validation_report,
                "cleaning_report": {
                    "input_rows": int(len(df)),
                    "retained_rows": int(len(cleaned)),
                    "dropped_rows": int(len(df) - len(cleaned)),
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
