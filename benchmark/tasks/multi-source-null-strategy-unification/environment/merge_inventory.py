from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from null_policy import standardize_value, to_numeric
from quality_summary import build_category_totals, build_source_null_summary
from supplier_schema import NUMERIC_COLUMNS, SUPPLIER_FILES

OUTPUT_PATH = Path("output.json")


def load_supplier(source: str, path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, keep_default_na=False)
    frame["source"] = source
    for column in NUMERIC_COLUMNS:
        frame[column] = frame[column].map(lambda value: standardize_value(source, column, value))
        frame[column] = to_numeric(frame[column])
    return frame


def build_payload(frame: pd.DataFrame) -> dict:
    valid_price = frame["price"].dropna()
    return {
        "record_count": int(frame.shape[0]),
        "valid_price_count": int(valid_price.shape[0]),
        "missing_price_count": int(frame["price"].isna().sum()),
        "average_price": round(float(valid_price.mean()), 2) if not valid_price.empty else None,
        "total_stock": int(frame["stock"].dropna().sum()),
        "out_of_stock_count": int((frame["stock"] == 0).sum()),
        "source_null_summary": build_source_null_summary(frame),
        "category_totals": build_category_totals(frame),
    }


def run(output_path: Path = OUTPUT_PATH) -> dict:
    combined = pd.concat([load_supplier(source, path) for source, path in SUPPLIER_FILES.items()], ignore_index=True)
    payload = build_payload(combined)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
