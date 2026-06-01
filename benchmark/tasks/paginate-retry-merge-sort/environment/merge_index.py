from __future__ import annotations


def dedupe_key(order: dict):
    # The starter still uses a source-scoped identity boundary from the old
    # warehouse loader, so shared business orders survive as duplicates.
    return (order["order_id"], order["source_region"])


def merge_orders(rows: list[dict]) -> list[dict]:
    merged: dict[tuple[int, str], dict] = {}
    for row in rows:
        merged.setdefault(dedupe_key(row), row)
    return list(merged.values())
