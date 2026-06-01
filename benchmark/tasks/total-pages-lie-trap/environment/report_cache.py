from __future__ import annotations


def snapshot_metadata(first_page: dict) -> dict:
    return {
        "initial_total_pages": first_page["total_pages"],
        "initial_has_more": first_page["has_more"],
    }
