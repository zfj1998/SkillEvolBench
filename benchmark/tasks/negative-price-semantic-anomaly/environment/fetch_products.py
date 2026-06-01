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
            if should_keep_record(normalized):
                combined.append(normalized)
    output_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    return combined


if __name__ == "__main__":
    run()
