from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from inventory_cache import LastGoodPayloadCache
from transport_guard import decode_payload

API_URL = "http://localhost:5050/api/inventory"
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
    cache = LastGoodPayloadCache()
    combined: list[dict] = []
    for _ in range(TOTAL_BATCHES):
        response = session.get(API_URL, timeout=10)
        payload = decode_payload(response, cache, logger)
        if not payload:
            continue
        data = payload.get("data", [])
        if not data:
            continue
        cache.observe(payload)
        combined.extend(data)
    output_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    return combined


if __name__ == "__main__":
    run()
