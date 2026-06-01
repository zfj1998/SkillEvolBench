from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from date_parser import parse_display_dates
from ordering_policy import sort_logs

CSV_PATH = Path("server_logs.csv")
OUTPUT_PATH = Path("output.json")


def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    df = pd.read_csv(csv_path)
    df["parsed_date"] = parse_display_dates(df["date"])
    sorted_df = sort_logs(df)
    export_df = sorted_df.drop(columns=["parsed_date"], errors="ignore")
    payload = {
        "row_count": int(len(export_df)),
        "first_date": export_df.iloc[0]["date"],
        "last_date": export_df.iloc[-1]["date"],
        "records": export_df.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
