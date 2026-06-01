from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from schema_casefold import resolve_metric_column

DEFAULT_SOURCE = Path("sales_data.csv")
OUTPUT_PATH = Path("output.json")


def run(source: Path | None = None, output_path: Path = OUTPUT_PATH) -> dict:
    csv_path = Path(os.environ.get("SALES_SOURCE", source or DEFAULT_SOURCE))
    df = pd.read_csv(csv_path)
    metric_column = resolve_metric_column(df.columns, "amount")
    total = round(float(pd.to_numeric(df[metric_column], errors="raise").sum()), 2)
    payload = {
        "metric_column": metric_column,
        "total_amount": total,
        "row_count": int(len(df)),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
