from __future__ import annotations


def merge_page(existing_rows: list[dict], page_rows: list[dict]) -> list[dict]:
    # The starter still trusts the API not to repeat user ids across pages.
    existing_rows.extend(page_rows)
    return existing_rows
