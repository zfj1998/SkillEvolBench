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
    "product_ordering.py": dedent(
        """
        from __future__ import annotations


        def product_sort_key(product_id: str) -> int:
            return int(str(product_id).strip().removeprefix("P"))
        """
    ),
    "dedup_policy.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd


        def deduplicate_transactions(df: pd.DataFrame) -> pd.DataFrame:
            return df.drop_duplicates(subset=["date", "product_id", "customer_id", "amount", "quantity", "channel"]).copy()
        """
    ),
    "process_transaction_log.py": dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path

        import pandas as pd

        from date_normalizer import parse_dates
        from dedup_policy import deduplicate_transactions
        from product_ordering import product_sort_key

        CSV_PATH = Path("transaction_log.csv")
        OUTPUT_PATH = Path("output.json")


        def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
            df = pd.read_csv(csv_path, dtype={"product_id": str})
            df["parsed_date"] = parse_dates(df["date"])
            df["amount_clean"] = (
                df["amount"].astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False).astype(float)
            )
            deduped = deduplicate_transactions(df)
            aggregated = (
                deduped.groupby(["parsed_date", "product_id"], as_index=False)["amount_clean"]
                .sum()
                .rename(columns={"amount_clean": "total_amount"})
            )
            aggregated["product_sort_key"] = aggregated["product_id"].map(product_sort_key)
            ordered = aggregated.sort_values(["parsed_date", "product_sort_key"], ascending=[True, True], kind="mergesort").reset_index(drop=True)
            ordered["date"] = ordered["parsed_date"].dt.strftime("%Y-%m-%d")
            export_df = ordered.drop(columns=["product_sort_key", "parsed_date"], errors="ignore")
            payload = {
                "row_count": int(len(export_df)),
                "records": export_df.to_dict(orient="records"),
            }
            output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
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
