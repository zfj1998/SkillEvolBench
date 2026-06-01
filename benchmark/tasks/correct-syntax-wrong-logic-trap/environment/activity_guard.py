from __future__ import annotations


def has_order_activity(row: dict[str, object]) -> bool:
    return row.get("order_id") is not None
