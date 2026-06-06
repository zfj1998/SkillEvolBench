#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "fetch_products.py": dedent(
        """
        from __future__ import annotations

        import json
        import logging
        from pathlib import Path

        import requests

        from catalog_contract import extract_products, response_is_usable

        API_URL = "http://localhost:5050/api/products"
        TOTAL_BATCHES = 10
        OUTPUT_PATH = Path("output.json")

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler("fetch_products.log"), logging.StreamHandler()],
        )
        logger = logging.getLogger(__name__)


        def run(output_path: Path = OUTPUT_PATH) -> list[dict]:
            session = requests.Session()
            combined: list[dict] = []
            seen_ids: set[int] = set()

            for batch_index in range(TOTAL_BATCHES):
                response = session.get(API_URL, timeout=10)
                payload = response.json()
                products = extract_products(payload, batch_index + 1, logger)
                if not products:
                    continue
                for product in products:
                    if product["id"] in seen_ids:
                        continue
                    combined.append(product)
                    seen_ids.add(product["id"])

            output_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
            return combined


        if __name__ == "__main__":
            run()
        """
    ),
    "catalog_contract.py": dedent(
        """
        from __future__ import annotations

        REQUIRED_KEYS = {"id", "name", "price", "currency", "in_stock", "batch"}


        def response_is_usable(payload: dict) -> bool:
            return payload.get("status") == "ok" and "data" in payload


        def extract_products(payload: dict, batch_number: int, logger) -> list[dict]:
            if not response_is_usable(payload):
                logger.warning("batch %s missing data payload", batch_number)
                return []

            data = payload.get("data")
            if not isinstance(data, list):
                logger.warning("batch %s data is %s instead of list", batch_number, type(data).__name__)
                return []

            clean = []
            for item in data:
                if isinstance(item, dict) and REQUIRED_KEYS.issubset(item):
                    clean.append(item)
                else:
                    logger.warning("batch %s item failed schema validation", batch_number)
            return clean
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
