from __future__ import annotations


def to_usd(amount: float, currency: str, rates: dict[str, float]) -> float:
    return round(float(amount) * rates[currency], 2)
