from __future__ import annotations


def totals_consistent(overall_total: float, by_product_line_total: float) -> bool:
    if overall_total <= 0:
        return False
    return abs(by_product_line_total - overall_total) / overall_total <= 0.25
