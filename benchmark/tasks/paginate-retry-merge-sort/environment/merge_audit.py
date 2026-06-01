from __future__ import annotations


def looks_complete(row_count: int, minimum_rows: int = 100) -> bool:
    return row_count >= minimum_rows
