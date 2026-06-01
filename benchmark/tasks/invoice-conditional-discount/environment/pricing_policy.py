from __future__ import annotations


DISCOUNT_CONDITION = "Orders over $1,000 receive 5% discount"


def should_apply_discount(subtotal: float | None, discount_amount: float | None, strict: bool = True) -> bool:
    if subtotal is None:
        return False
    if strict:
        threshold_ok = subtotal > 1000.0
    else:
        threshold_ok = subtotal >= 1000.0
    return bool(threshold_ok and (discount_amount or 0.0) > 0.0)


def tax_base_after_discount(subtotal: float | None, discount_amount: float | None) -> float | None:
    if subtotal is None:
        return None
    return round(subtotal - (discount_amount or 0.0), 2)
