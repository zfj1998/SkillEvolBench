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
        "checks": validation_report,
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
