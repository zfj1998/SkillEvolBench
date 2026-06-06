#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/solution.py" <<'__SKILL_EVOL_REFERENCE_SOLUTION_PY_0__'
from __future__ import annotations

import json
from pathlib import Path

from mock_api import build_api

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output.json"
TRACE = HERE / "trace.json"


def solve(api):
    cursor = None
    orders = []
    seen_ids = set()
    expected_total = None

    while True:
        response = api.fetch_orders(cursor=cursor)
        expected_total = response["total"]
        for order in response["data"]:
            order_id = order["id"]
            if order_id in seen_ids:
                continue
            seen_ids.add(order_id)
            orders.append(order)
        if response["next_cursor"] is None:
            break
        cursor = response["next_cursor"]

    if expected_total is not None and len(orders) != expected_total:
        raise ValueError(f"expected {expected_total} orders, got {len(orders)}")
    return orders


def main():
    api = build_api()
    result = solve(api)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    TRACE.write_text(json.dumps(api.export_state(), indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_SOLUTION_PY_0__
cat <<'PY' > "$PROJECT_ROOT/consistency_guard.py"
from __future__ import annotations


def should_restart(previous_total: int | None, current_total: int) -> bool:
    if previous_total is None:
        return False
    return current_total != previous_total
PY
cat <<'PY' > "$PROJECT_ROOT/order_buffer.py"
from __future__ import annotations


def append_page(existing_rows: list[dict], page_rows: list[dict]) -> list[dict]:
    seen_ids = {row["id"] for row in existing_rows}
    for row in page_rows:
        row_id = row["id"]
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        existing_rows.append(row)
    return existing_rows
PY
echo "Oracle solution applied for E2-LS3-T3."
