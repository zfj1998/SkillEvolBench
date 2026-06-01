from __future__ import annotations


def looks_reasonable(row_count: int, minimum_rows: int = 50) -> bool:
    return row_count >= minimum_rows
