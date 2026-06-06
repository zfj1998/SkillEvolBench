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

        from pricing_rules import normalize_record, should_keep_record

        API_URL = "http://localhost:5050/api/pricing"
        TOTAL_BATCHES = 4
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
            for _ in range(TOTAL_BATCHES):
                response = session.get(API_URL, timeout=10)
                payload = response.json()
                for record in payload.get("data", []):
                    normalized = normalize_record(record)
                    if should_keep_record(normalized, logger):
                        combined.append(normalized)
            output_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
            return combined


        if __name__ == "__main__":
            run()
        """
    ),
    "pricing_rules.py": dedent(
        """
        from __future__ import annotations

        REQUIRED_KEYS = {"id", "name", "price", "currency", "in_stock"}


        def normalize_record(record: dict) -> dict:
            return dict(record)


        def should_keep_record(record: dict, logger) -> bool:
            if not isinstance(record, dict):
                return False
            if not REQUIRED_KEYS.issubset(record):
                logger.warning("record missing required fields")
                return False
            price = record.get("price")
            if not isinstance(price, (int, float)):
                logger.warning("record has non-numeric price")
                return False
            if price < 0:
                logger.warning("negative price filtered for id=%s", record.get("id"))
                return False
            return True
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
