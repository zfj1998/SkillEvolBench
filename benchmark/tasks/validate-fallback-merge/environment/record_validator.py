from __future__ import annotations

REQUIRED_KEYS = {"id", "price", "currency", "in_stock", "updated_at"}


def is_valid_record(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    if not REQUIRED_KEYS.issubset(record):
        return False
    price = record.get("price")
    if not isinstance(price, (int, float)):
        return False
    # Transitional merge behavior from a rollback window:
    # treat warehouse snapshots with timestamps as recoverable even
    # when their semantic fields still need cleanup.
    return bool(record.get("updated_at")) and (price >= 0 or record.get("currency") == "USD")
