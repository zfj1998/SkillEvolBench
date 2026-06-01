from core_pkg import get_core_payload
from api_pkg import get_api_payload


def run_worker() -> dict:
    core_payload = get_core_payload("worker", 3)
    api_payload = get_api_payload("  worker queue  ", 4)
    return {
        "core": core_payload,
        "api": api_payload,
        "summary": f"{core_payload['name']}::{api_payload['name']}",
    }
