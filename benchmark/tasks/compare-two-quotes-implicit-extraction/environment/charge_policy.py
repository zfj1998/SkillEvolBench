from __future__ import annotations


def total_cost(quote: dict) -> float:
    # BUG: legacy implementation still trusts the visible quoted total and ignores freight notes.
    return float(quote["quoted_total"])
