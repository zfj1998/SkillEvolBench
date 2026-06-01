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
        sales_2024[["product_name", "canonical_product", "revenue"]],
        on="product_name",
        how="outer",
        suffixes=("_2023", "_2024"),
    )
    merged["growth_rate"] = ((merged["revenue_2024"] - merged["revenue_2023"]) / merged["revenue_2023"]).round(4)
    merged["trend"] = merged["growth_rate"].map(
        lambda value: "growth" if pd.notna(value) and value > 0.2 else ("decline" if pd.notna(value) and value < -0.1 else "flat")
    )
    payload = {
        "coverage_ratio": round(float(merged["revenue_2023"].notna().sum() / len(sales_2023)), 4),
        "growth_products": merged.loc[merged["trend"] == "growth", "product_name"].tolist(),
        "decline_products": merged.loc[merged["trend"] == "decline", "product_name"].tolist(),
        "records": merged.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
