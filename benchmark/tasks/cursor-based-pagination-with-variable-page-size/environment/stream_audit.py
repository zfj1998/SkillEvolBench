from __future__ import annotations


def looks_complete(row_count: int, expected_total: int) -> bool:
    # The starter only checks for "enough rows" and ignores duplicate ids.
    return row_count >= expected_total
