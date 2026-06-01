from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from sort_contract import attach_feed_order
from tie_break_policy import order_employees

CSV_PATH = Path("employees.csv")
OUTPUT_PATH = Path("output.json")


def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    df = pd.read_csv(csv_path)
    df = attach_feed_order(df)
    ordered = order_employees(df)
    payload = {
        "row_count": int(len(ordered)),
        "records": ordered.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
