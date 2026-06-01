from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from fallback_client import fetch_backup_record
from merge_policy import merge_records
from record_validator import is_valid_record

PRIMARY_URL = "http://localhost:5050/api/products"
OUTPUT_PATH = Path("output.json")
TOTAL_BATCHES = 4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("fetch_products.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def run(output_path: Path = OUTPUT_PATH) -> list[dict]:
    session = requests.Session()
    primary_records: list[dict] = []
    invalid_ids: set[int] = set()
    for _ in range(TOTAL_BATCHES):
        response = session.get(PRIMARY_URL, timeout=10)
        payload = response.json()
        for record in payload.get("data", []):
            primary_records.append(record)
            if not is_valid_record(record):
                invalid_ids.add(record["id"])

    merged = merge_records(primary_records, invalid_ids, lambda pid: fetch_backup_record(session, pid, logger))
    output_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


if __name__ == "__main__":
    run()
