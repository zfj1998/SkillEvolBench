from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from collation_policy import german_sort_key
from export_profile import contact_sort_columns

CSV_PATH = Path("german_contacts.csv")
OUTPUT_PATH = Path("output.json")


def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    df = pd.read_csv(csv_path)
    columns = contact_sort_columns()
    df = df.assign(
        _last_sort=df["last_name"].map(german_sort_key),
        _first_sort=df["first_name"].map(german_sort_key),
    )
    sorted_df = df.sort_values(["_last_sort", "_first_sort", "contact_id"], kind="mergesort").drop(columns=["_last_sort", "_first_sort"])
    payload = {
        "row_count": int(len(sorted_df)),
        "records": sorted_df.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
