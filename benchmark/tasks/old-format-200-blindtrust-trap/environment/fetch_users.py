from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from compat_projection import project_user
from field_aliases import load_contract

API_URL = "http://localhost:5050/api/users"
TOTAL_BATCHES = 2
OUTPUT_PATH = Path("output.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("fetch_users.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def run(output_path: Path = OUTPUT_PATH) -> list[dict]:
    contract = {
        "canonical_fields": ["id", "username", "phone", "email", "created_at"],
        "deprecated": {
            "username": "user_name",
            "phone": "phone_number",
            "email": "email_address",
            "created_at": "created_date",
        },
        "compat_mode": "dual-read",
    }
    session = requests.Session()
    users: list[dict] = []
    for _ in range(TOTAL_BATCHES):
        response = session.get(API_URL, timeout=10)
        payload = response.json()
        for item in payload.get("data", []):
            users.append(project_user(item, contract))
    output_path.write_text(json.dumps(users, indent=2), encoding="utf-8")
    return users


if __name__ == "__main__":
    run()
