from __future__ import annotations

import json
from pathlib import Path

from amount_contract import compute_amount_summary, load_orders
from sanity_audit import build_sanity_checks

ORDERS_PATH = Path("orders.csv")
OUTPUT_PATH = Path("output.json")


def run(orders_path: Path = ORDERS_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    orders = load_orders(orders_path)
    summary = compute_amount_summary(orders)
    payload = {
        **summary,
        "sanity_checks": build_sanity_checks(summary),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
