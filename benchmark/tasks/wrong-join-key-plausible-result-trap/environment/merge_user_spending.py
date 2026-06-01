from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from join_selector import choose_join_columns
from schema_cleaner import clean_transactions, clean_users

USERS_PATH = Path("users.csv")
TRANSACTIONS_PATH = Path("transactions.csv")
OUTPUT_PATH = Path("output.json")


def run(users_path: Path = USERS_PATH, transactions_path: Path = TRANSACTIONS_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    users = clean_users(pd.read_csv(users_path))
    transactions = clean_transactions(pd.read_csv(transactions_path))
    left_key, right_key = choose_join_columns(users.columns.tolist(), transactions.columns.tolist())
    users = users.rename(columns={"id": "user_id_master"})
    transactions = transactions.rename(columns={"id": "transaction_id"})
    left_key = "user_id_master" if left_key == "id" else left_key
    right_key = "transaction_id" if right_key == "id" else right_key
    merged = users.merge(transactions, left_on=left_key, right_on=right_key, how="inner")
    spending = (
        merged.groupby(["user_id_master", "name"], as_index=False)
        .agg(transaction_count=("amount", "size"), total_spending=("amount", "sum"))
        .sort_values("user_id_master", kind="mergesort")
        .reset_index(drop=True)
    )
    spending = spending.rename(columns={"user_id_master": "user_id"})
    payload = {
        "merged_row_count": int(len(merged)),
        "average_transactions_per_user": round(float(spending["transaction_count"].mean()), 4),
        "records": spending.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
