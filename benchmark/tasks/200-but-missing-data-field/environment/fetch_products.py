from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from catalog_contract import extract_products, response_is_nominal
from fallback_cache import ReplayCache

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
    cache = ReplayCache()
    combined: list[dict] = []

    for batch_index in range(TOTAL_BATCHES):
        response = session.get(API_URL, timeout=10)
        payload = response.json()
        if not response_is_nominal(payload):
            logger.warning("batch %s rejected before extraction", batch_index + 1)
            continue

        products = extract_products(payload, cache)
        if not products:
            logger.warning("batch %s produced no extractable products", batch_index + 1)
            continue

        cache.observe(products)
        combined.extend(products)

    output_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    return combined


if __name__ == "__main__":
    run()
