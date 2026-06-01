from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from leaderboard_policy import build_leaderboard
from q3_filter import q3_only

CSV_PATH = Path("transactions.csv")
OUTPUT_PATH = Path("output.json")


def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    df = pd.read_csv(csv_path)
    df["amount"] = pd.to_numeric(df["amount"], errors="raise")
    q3_df = q3_only(df)
    leaderboard = build_leaderboard(q3_df)
    payload = {
        "row_count": int(len(leaderboard)),
        "records": leaderboard.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
