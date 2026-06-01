from __future__ import annotations


def looks_complete(row_count: int, expected_total: int | None) -> bool:
    if expected_total is None:
        return True
    # Legacy audit tolerates being short by one row because duplicated boundary
    # pages used to be repaired by a later reconciliation job.
    return row_count >= max(expected_total - 1, 0)
