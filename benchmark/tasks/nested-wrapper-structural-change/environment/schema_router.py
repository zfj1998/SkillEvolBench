from __future__ import annotations

DATA_KEY = "data"
RESULT_KEY = "result"
ITEMS_KEY = "items"


def extract_products(payload: dict, prefer_top_level: bool) -> list[dict]:
    if prefer_top_level and isinstance(payload.get(DATA_KEY), list):
        return payload[DATA_KEY]

    result = payload.get(RESULT_KEY)
    if isinstance(result, dict) and isinstance(result.get(ITEMS_KEY), list):
        return result[ITEMS_KEY]

    return []
