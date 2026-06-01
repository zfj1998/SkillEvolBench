from __future__ import annotations


def append_page(existing_rows: list[dict], page_rows: list[dict]) -> list[dict]:
    existing_rows.extend(page_rows)
    return existing_rows
