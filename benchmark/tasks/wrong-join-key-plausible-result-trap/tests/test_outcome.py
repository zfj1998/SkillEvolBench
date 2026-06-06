from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "merge_user_spending.py"
USERS = PROJECT / "users.csv"
TRANSACTIONS = PROJECT / "transactions.csv"
OUTPUT = PROJECT / "output.json"


def _clean_string(value: object) -> str:
    return str(value).replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").strip()


def _expected():
    users = pd.read_csv(USERS)
    users.columns = [_clean_string(col).lower() for col in users.columns]
    users["id"] = pd.to_numeric(users["id"].map(_clean_string), errors="coerce")
    users["name"] = users["name"].map(_clean_string)
    users = users.dropna(subset=["id", "name"])
    users["id"] = users["id"].astype(int)
    users = users.rename(columns={"id": "user_id_master"})

    transactions = pd.read_csv(TRANSACTIONS)
    transactions.columns = [_clean_string(col).lower() for col in transactions.columns]
    transactions["id"] = pd.to_numeric(transactions["id"].map(_clean_string), errors="coerce")
    transactions["user_id"] = pd.to_numeric(transactions["user_id"].map(_clean_string), errors="coerce")
    transactions["amount"] = pd.to_numeric(
        transactions["amount"]
        .map(_clean_string)
        .astype(str)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )
    transactions = transactions.dropna(subset=["id", "user_id"])
    transactions = transactions.dropna(subset=["amount"])
    transactions["id"] = transactions["id"].astype(int)
    transactions["user_id"] = transactions["user_id"].astype(int)
    transactions = transactions.rename(columns={"id": "transaction_id"})

    merged = users.merge(transactions, left_on="user_id_master", right_on="user_id", how="inner")
    spending = (
        merged.groupby(["user_id_master", "name"], as_index=False)
        .agg(transaction_count=("amount", "size"), total_spending=("amount", "sum"))
        .sort_values("user_id_master", kind="mergesort")
        .reset_index(drop=True)
    )
    spending = spending.rename(columns={"user_id_master": "user_id"})
    return merged, spending


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    merged, spending = _expected()
    public = run_checks("public", [
        ("non_empty_output", lambda: len(_run()[1].get("records", [])) > 0 or (_ for _ in ()).throw(AssertionError("no spending records produced"))),
    ])
    hidden = run_checks("hidden", [
        ("merged_row_count_matches_transactions", lambda: abs(_run()[1].get("merged_row_count", 0) - len(merged)) <= 5 or (_ for _ in ()).throw(AssertionError("merged row count indicates wrong join key"))),
        ("average_transactions_per_user_correct", lambda: abs(_run()[1].get("average_transactions_per_user", 0) - float(spending["transaction_count"].mean())) <= 0.05 or (_ for _ in ()).throw(AssertionError("average transactions per user incorrect"))),
        ("totals_match_ground_truth", lambda: _run()[1].get("records", [])[:25] == spending.to_dict(orient="records")[:25] or (_ for _ in ()).throw(AssertionError("spending totals mismatch"))),
        ("not_one_transaction_per_user", lambda: _run()[1].get("average_transactions_per_user", 0) > 2.0 or (_ for _ in ()).throw(AssertionError("join collapsed to one transaction per user"))),
    ])
    return emit_report("E3-LS3-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
