from __future__ import annotations


def normalize_record(record: dict) -> dict:
    normalized = dict(record)
    price = normalized.get("price")
    if normalized.get("discount_applied") and isinstance(price, (int, float)):
        normalized["price"] = abs(price)
    return normalized


def should_keep_record(record: dict) -> bool:
    return isinstance(record, dict) and "price" in record
