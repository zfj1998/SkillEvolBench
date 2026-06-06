from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "merge_customers.py"
CUSTOMERS = PROJECT / "customers.csv"
ORDERS = PROJECT / "orders_summary.csv"
OUTPUT = PROJECT / "output.json"


def _expected() -> pd.DataFrame:
    customers = pd.read_csv(CUSTOMERS)
    orders = pd.read_csv(ORDERS)
    merged = customers.merge(orders, on="customer_id", how="left", validate="1:1")
    merged["has_orders"] = merged["total_orders"].notna()
    merged["total_orders"] = merged["total_orders"].fillna(0).astype(int)
    merged["total_amount"] = merged["total_amount"].fillna(0.0).round(2)
    merged["last_order_date"] = merged["last_order_date"].fillna("")
    return merged


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    public = run_checks("public", [
        ("row_count_1000", lambda: _run()[1].get("row_count") == 1000 or (_ for _ in ()).throw(AssertionError("expected 1000 customers"))),
        ("total_orders_present", lambda: "total_orders" in _run()[1].get("records", [{}])[0] or (_ for _ in ()).throw(AssertionError("missing total_orders column"))),
    ])
    hidden = run_checks("hidden", [
        ("all_customers_preserved", lambda: sorted(record["customer_id"] for record in _run()[1].get("records", [])) == expected["customer_id"].tolist() or (_ for _ in ()).throw(AssertionError("left join did not preserve all customers"))),
        ("unmatched_reported", lambda: _run()[1].get("unmatched_customers", {}).get("missing_count") == 200 or (_ for _ in ()).throw(AssertionError("expected 200 unmatched customers"))),
        ("matched_amounts_correct", lambda: _run()[1].get("records", [])[0:25] == expected.to_dict(orient="records")[0:25] or (_ for _ in ()).throw(AssertionError("merged values incorrect"))),
        ("no_duplicate_customer_ids", lambda: len({record["customer_id"] for record in _run()[1].get("records", [])}) == 1000 or (_ for _ in ()).throw(AssertionError("duplicate customer ids detected"))),
    ])
    return emit_report("E3-LS3-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
