from __future__ import annotations


def sort_orders(rows: list[dict]) -> list[dict]:
    # The starter still relies on raw string sorting even though regional feeds
    # emit timezone-aware timestamps in their local offsets.
    return sorted(rows, key=lambda item: item["created_at"])
