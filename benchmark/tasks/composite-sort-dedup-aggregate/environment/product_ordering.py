from __future__ import annotations


def product_sort_key(product_id: str) -> str:
    return str(product_id).strip()
