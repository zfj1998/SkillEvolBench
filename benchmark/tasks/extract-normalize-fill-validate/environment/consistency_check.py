from __future__ import annotations


def totals_match(pdf_total: float, items: list[dict]) -> bool:
    calculated = round(sum(item["amount"] for item in items), 2)
    return abs(calculated - pdf_total) <= 0.01
