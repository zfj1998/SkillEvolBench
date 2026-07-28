from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_transaction_log.py"
CSV_PATH = PROJECT / "transaction_log.csv"
OUTPUT = PROJECT / "output.json"


def _expected():
    df = pd.read_csv(CSV_PATH, dtype={"product_id": str})
    df["parsed_date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount_clean"] = df["amount"].astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False).astype(float)
    deduped = df.drop_duplicates(subset=["date", "product_id", "customer_id", "amount", "quantity", "channel"]).copy()
    aggregated = (
        deduped.groupby(["parsed_date", "product_id"], as_index=False)["amount_clean"]
        .sum()
        .rename(columns={"amount_clean": "total_amount"})
    )
    aggregated["_product_order"] = aggregated["product_id"].map(lambda value: int(str(value).strip().removeprefix("P")))
    ordered = aggregated.sort_values(["parsed_date", "_product_order"], ascending=[True, True], kind="mergesort").reset_index(drop=True)
    ordered["date"] = ordered["parsed_date"].dt.strftime("%Y-%m-%d")
    return ordered.drop(columns=["_product_order", "parsed_date"])


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def _required_record_projection(records):
    """Compare the required contract while allowing documented aggregate fields."""
    return [
        {
            "product_id": item.get("product_id"),
            "date": item.get("date"),
            "total_amount": item.get("total_amount"),
        }
        for item in records
    ]


def run():
    expected = _expected()
    expected_records = expected.to_dict(orient="records")
    public = run_checks("public", [
        ("records_present", lambda: len(_run()[1].get("records", [])) > 0 or (_ for _ in ()).throw(AssertionError("records missing"))),
        ("row_count_present", lambda: _run()[1].get("row_count") == len(expected) or (_ for _ in ()).throw(AssertionError("row count mismatch"))),
    ])
    hidden = run_checks("hidden", [
        (
            "date_sort_correct",
            lambda: _required_record_projection(_run()[1].get("records", []))
            == expected_records
            or (_ for _ in ()).throw(
                AssertionError("required record values or composite ordering mismatch")
            ),
        ),
        ("natural_product_order_correct", lambda: [r["product_id"] for r in _run()[1].get("records", [])] == expected["product_id"].tolist() or (_ for _ in ()).throw(AssertionError("product natural ordering wrong"))),
        ("semantic_duplicates_removed", lambda: _run()[1].get("row_count") == len(expected) or (_ for _ in ()).throw(AssertionError("duplicates not removed correctly"))),
        ("aggregates_correct", lambda: bool(_run()[1].get("records", [{}])[0].get("total_amount") == expected.iloc[0]["total_amount"]) or (_ for _ in ()).throw(AssertionError("aggregated totals incorrect"))),
    ])
    return emit_report("E3-LS2-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
