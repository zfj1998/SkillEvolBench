from __future__ import annotations

import json
from pathlib import Path

from merge_audit import looks_complete
from merge_index import merge_orders
from mock_api import build_api
from ordering_policy import sort_orders
from regional_sync import fetch_region

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output.json"
TRACE = HERE / "trace.json"

def solve(api):
    combined = fetch_region(api, "us") + fetch_region(api, "eu")
    result = sort_orders(merge_orders(combined))
    if not looks_complete(len(result)):
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
