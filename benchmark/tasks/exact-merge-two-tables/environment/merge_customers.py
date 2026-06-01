from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from join_audit import summarize_unmatched_customers
from merge_contract import merge_customer_orders

CUSTOMERS_PATH = Path("customers.csv")
ORDERS_PATH = Path("orders_summary.csv")
OUTPUT_PATH = Path("output.json")


def run(
    customers_path: Path = CUSTOMERS_PATH,
    orders_path: Path = ORDERS_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict:
    customers = pd.read_csv(customers_path)
    orders = pd.read_csv(orders_path)
    merged = merge_customer_orders(customers, orders)
    payload = {
        "row_count": int(len(merged)),
        "unmatched_customers": summarize_unmatched_customers(merged),
        "records": merged.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
