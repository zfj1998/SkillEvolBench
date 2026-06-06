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
    page = 1
    products = []

    while True:
        response = api.get_products(page=page)
        products.extend(response["data"])
        if not response["has_more"]:
            break
        page += 1

    if len(products) != 120:
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
__SKILL_EVOL_REFERENCE_SOLUTION_PY_0__
echo "Oracle solution applied for E2-LS3-T4."
