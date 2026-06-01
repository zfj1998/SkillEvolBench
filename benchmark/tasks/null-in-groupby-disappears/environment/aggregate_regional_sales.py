from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aggregation_audit import build_reconciliation
from region_normalizer import normalize_region

INPUT_PATH = Path("regional_sales.csv")
OUTPUT_PATH = Path("output.json")


def run(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    frame = pd.read_csv(input_path)
    frame["amount"] = pd.to_numeric(frame["amount"].astype(str).str.replace(",", "", regex=False), errors="coerce")
    frame["normalized_region"] = frame["region"].map(normalize_region)
    grouped = (
        frame.groupby("normalized_region", as_index=False)["amount"]
        .sum()
        .rename(columns={"normalized_region": "region", "amount": "total_amount"})
        .sort_values("region", kind="mergesort", na_position="last")
    )
    source_total = float(frame["amount"].sum())
    grouped_total = float(grouped["total_amount"].sum())
    payload = {
        "records": grouped.to_dict(orient="records"),
        "source_total": round(source_total, 2),
        "grouped_total": round(grouped_total, 2),
        "unresolved_row_count": int(frame["normalized_region"].isna().sum()),
        "reconciliation": build_reconciliation(source_total, grouped_total),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
