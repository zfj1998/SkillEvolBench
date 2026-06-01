from __future__ import annotations


EXPECTED_MIN = 450
EXPECTED_MAX = 1200


def evaluate_rowcount(row_count: int) -> dict[str, object]:
    return {
        "expected_min": EXPECTED_MIN,
        "expected_max": EXPECTED_MAX,
        "rowcount_reasonable": EXPECTED_MIN <= row_count <= EXPECTED_MAX,
    }
