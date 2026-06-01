from __future__ import annotations


def build_fetch_plan(first_page: dict) -> list[int]:
    total_pages = first_page["total_pages"]
    return list(range(2, total_pages + 1))
