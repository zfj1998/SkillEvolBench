from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from catalog_sort import order_catalog
from id_normalizer import normalize_product_id

CSV_PATH = Path("products.csv")
OUTPUT_PATH = Path("output.json")


def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    df = pd.read_csv(csv_path, dtype={"product_id": str})
    df["product_id_normalized"] = df["product_id"].map(normalize_product_id)
    ordered = order_catalog(df)
    payload = {
        "row_count": int(len(ordered)),
        "records": ordered.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
