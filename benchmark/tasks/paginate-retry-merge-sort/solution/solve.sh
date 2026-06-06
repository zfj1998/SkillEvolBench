#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/solution.py" <<'__SKILL_EVOL_REFERENCE_SOLUTION_PY_0__'
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from mock_api import build_api

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output.json"
TRACE = HERE / "trace.json"


def _fetch_region(api, region):
    page = 1
    rows = []

    while True:
        attempts = 0
        while True:
            response = api.fetch_orders(region=region, page=page)
            if response["status"] == 200:
                break
            if response["status"] != 503 or attempts >= 2:
                raise RuntimeError(f"failed to fetch {region} page {page}")
            attempts += 1
        rows.extend(response["data"])
        if not response["has_more"]:
            break
        page += 1

    return rows


def solve(api):
    combined = _fetch_region(api, "us") + _fetch_region(api, "eu")
    deduped = {}
    for order in combined:
        deduped.setdefault(order["order_id"], order)
    result = sorted(deduped.values(), key=lambda item: datetime.fromisoformat(item["created_at"]))
    if len(result) != 120:
        raise ValueError(f"expected 120 merged orders, got {len(result)}")
    return result


def main():
    api = build_api()
    result = solve(api)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    TRACE.write_text(json.dumps(api.export_state(), indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_SOLUTION_PY_0__
cat <<'PY' > "$PROJECT_ROOT/merge_index.py"
from __future__ import annotations


def dedupe_key(order: dict):
    return order["order_id"]


def merge_orders(rows: list[dict]) -> list[dict]:
    merged: dict[int, dict] = {}
    for row in rows:
        merged.setdefault(dedupe_key(row), row)
    return list(merged.values())
PY
cat <<'PY' > "$PROJECT_ROOT/ordering_policy.py"
from __future__ import annotations

from datetime import datetime


def sort_orders(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda item: datetime.fromisoformat(item["created_at"]))
PY
echo "Oracle solution applied for E2-LS3-T6."
