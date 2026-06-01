from __future__ import annotations


def prefer_top_level_data(payload: dict) -> bool:
    return payload.get("data_contract") == "transitional" and "data" in payload
