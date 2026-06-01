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
        deduped.groupby(["date", "product_id"], as_index=False)["amount_clean"]
        .sum()
        .rename(columns={"amount_clean": "total_amount"})
    )
    aggregated["product_sort_key"] = aggregated["product_id"].map(product_sort_key)
    ordered = aggregated.sort_values(["date", "product_sort_key"], ascending=[True, True], kind="mergesort").reset_index(drop=True)
    payload = {
        "row_count": int(len(ordered)),
        "records": ordered.drop(columns=["product_sort_key"]).to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
