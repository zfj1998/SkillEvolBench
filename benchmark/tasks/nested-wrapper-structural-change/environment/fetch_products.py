from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from rollout_policy import prefer_top_level_data
from schema_router import extract_products

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
        products = extract_products(payload, prefer_top_level_data(payload))
        for product in products:
            if product["id"] in seen_ids:
                continue
            combined.append(product)
            seen_ids.add(product["id"])
    output_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    return combined


if __name__ == "__main__":
    run()
