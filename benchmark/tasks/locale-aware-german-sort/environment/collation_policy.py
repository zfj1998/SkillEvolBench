from __future__ import annotations


def german_sort_key(text: str) -> str:
    # Legacy compromise used during migration from ASCII-only exports. It lowercases
    # correctly but keeps umlauts as-is, which is not German phonebook ordering.
    return str(text).casefold()
