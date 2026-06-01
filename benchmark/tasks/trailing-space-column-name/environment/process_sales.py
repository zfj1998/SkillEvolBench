from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aggregation_plan import build_summary_frame
from schema_registry import require_canonical_columns

CSV_PATH = Path("sales.csv")
OUTPUT_PATH = Path("output.json")


def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    df = pd.read_csv(csv_path)
    column_map = require_canonical_columns(df.columns)
    df = df.rename(columns={actual: canonical for canonical, actual in column_map.items()})

    summary_rows = []
    for _, row in build_summary_frame(df).iterrows():
        summary_rows.append(
            {
                "name": row["name"],
                "total_amount": round(float(row["sum"]), 2),
                "average_amount": round(float(row["mean"]), 2),
                "transaction_count": int(row["count"]),
            }
        )

    payload = {
        "summary": summary_rows,
        "grand_total": round(float(df["amount"].sum()), 2),
        "row_count": int(len(df)),
        "schema_report": {
            "raw_columns": list(df.columns),
            "canonical_columns": list(column_map.keys()),
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
