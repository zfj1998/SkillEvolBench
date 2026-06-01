from __future__ import annotations


def looks_complete(collected_count: int, expected_total: int, page_window: int = 25) -> bool:
    # The starter still stops when it gets "within one page" of the expected total.
    return collected_count >= max(expected_total - page_window, 0)
