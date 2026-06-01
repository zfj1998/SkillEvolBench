from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from join_plan import build_region_totals, merge_orders
from key_contract import normalize_dimension_key, normalize_fact_key

USERS_PATH = Path("users.csv")
ORDERS_PATH = Path("orders.csv")
OUTPUT_PATH = Path("output.json")


def run(
    users_path: Path = USERS_PATH,
    orders_path: Path = ORDERS_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict:
    users = pd.read_csv(users_path)
    orders = pd.read_csv(orders_path)

    key_report = {
        "users_dtype_before": str(users["user_id"].dtype),
        "orders_dtype_before": str(orders["user_id"].dtype),
    }

    users["user_id"] = normalize_dimension_key(users["user_id"])
    orders["user_id"] = normalize_fact_key(orders["user_id"])

    key_report["users_dtype_after"] = str(users["user_id"].dtype)
    key_report["orders_dtype_after"] = str(orders["user_id"].dtype)

    merged = merge_orders(users, orders)
    payload = {
        "region_totals": build_region_totals(merged),
        "merged_row_count": int(len(merged)),
        "merge_report": {
            **key_report,
            "unmatched_orders": int(len(orders) - len(merged)),
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
