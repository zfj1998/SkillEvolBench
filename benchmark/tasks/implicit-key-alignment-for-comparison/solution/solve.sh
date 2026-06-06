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
    "product_aliases.py": dedent(
        """
        from __future__ import annotations

        PRODUCT_ALIASES = {
            "ultra hd smart television 55 inch": "ultra hd smart television 55-inch",
            "ultra hd smart television 55-inch": "ultra hd smart television 55-inch",
            "wireless bluetooth noise cancelling headphones": "wireless bluetooth noise cancelling headphones",
            "wireless bluetooth noise-cancelling headphones": "wireless bluetooth noise cancelling headphones",
        }
        """
    ),
    "snapshot_cleaner.py": dedent(
        """
        from __future__ import annotations

        import re

        import pandas as pd

        from product_aliases import PRODUCT_ALIASES


        def canonical_product_name(value: str) -> str:
            normalized = str(value).replace("\\u200b", "").strip().lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\\s+", " ", normalized).strip()
            return PRODUCT_ALIASES.get(normalized, normalized)


        def prepare_snapshot(df: pd.DataFrame, revenue_column: str = "revenue") -> pd.DataFrame:
            prepared = df.copy()
            prepared["canonical_product"] = prepared["product_name"].map(canonical_product_name)
            prepared[revenue_column] = pd.to_numeric(
                prepared[revenue_column]
                .astype(str)
                .str.replace("(", "-", regex=False)
                .str.replace(")", "", regex=False)
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip(),
                errors="coerce",
            )
            prepared["snapshot_rank"] = prepared["snapshot_id"].astype(str)
            prepared = prepared.sort_values(["canonical_product", "snapshot_rank"], kind="mergesort")
            prepared = prepared.drop_duplicates(subset=["canonical_product"], keep="last").copy()
            return prepared
        """
    ),
    "compare_sales.py": dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path

        import pandas as pd

        from snapshot_cleaner import prepare_snapshot

        SALES_2023 = Path("sales_2023.csv")
        SALES_2024 = Path("sales_2024.csv")
        OUTPUT_PATH = Path("output.json")


        def run(path_2023: Path = SALES_2023, path_2024: Path = SALES_2024, output_path: Path = OUTPUT_PATH) -> dict:
            sales_2023 = prepare_snapshot(pd.read_csv(path_2023), revenue_column="revenue")
            sales_2024 = prepare_snapshot(pd.read_csv(path_2024), revenue_column="revenue")
            merged = sales_2023.merge(
                sales_2024[["canonical_product", "revenue"]],
                on="canonical_product",
                how="outer",
                suffixes=("_2023", "_2024"),
            )
            merged["growth_rate"] = ((merged["revenue_2024"] - merged["revenue_2023"]) / merged["revenue_2023"]).round(4)
            merged["trend"] = merged["growth_rate"].map(
                lambda value: "growth" if pd.notna(value) and value > 0.2 else ("decline" if pd.notna(value) and value < -0.1 else "flat")
            )
            payload = {
                "coverage_ratio": round(float((merged["revenue_2023"].notna() & merged["revenue_2024"].notna()).sum() / len(sales_2023)), 4),
                "growth_products": merged.loc[merged["trend"] == "growth", "canonical_product"].tolist(),
                "decline_products": merged.loc[merged["trend"] == "decline", "canonical_product"].tolist(),
                "records": merged.to_dict(orient="records"),
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
