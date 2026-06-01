from __future__ import annotations

import json
from pathlib import Path

from mock_api import build_api
from consistency_guard import should_restart
from order_buffer import append_page
from scan_strategy import DEFAULT_LIMIT, initial_request, next_offset

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output.json"
TRACE = HERE / "trace.json"


def solve(api):
    request = initial_request()
    orders = []
    previous_total = None

    while True:
        response = api.fetch_orders(**request)
        if should_restart(previous_total, response["total"]):
            request = initial_request()
            orders = []
            previous_total = None
            continue
        previous_total = response["total"]
        append_page(orders, response["data"])
        if not response["has_more"]:
            break
        request = {
            "offset": next_offset(request["offset"], DEFAULT_LIMIT),
            "limit": DEFAULT_LIMIT,
        }
    return orders


def main():
    api = build_api()
    result = solve(api)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    TRACE.write_text(json.dumps(api.export_state(), indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
