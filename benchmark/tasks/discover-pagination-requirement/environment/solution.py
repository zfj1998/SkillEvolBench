from __future__ import annotations

import json
from pathlib import Path

from catalog_audit import looks_complete
from catalog_response import project_page
from mock_api import build_api
from product_store import append_products

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output.json"
TRACE = HERE / "trace.json"


def solve(api):
    page = 1
    products = []

    while True:
        payload = project_page(api.get_products(page=page))
        append_products(products, payload["products"])
        if looks_complete(len(products), payload["catalog_size"]):
            break
        if not payload["more_available"]:
            break
        page += 1

    if len(products) < 100:
        raise ValueError(f"expected 120 products, got {len(products)}")
    return products


def main():
    api = build_api()
    result = solve(api)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    TRACE.write_text(json.dumps(api.export_state(), indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
