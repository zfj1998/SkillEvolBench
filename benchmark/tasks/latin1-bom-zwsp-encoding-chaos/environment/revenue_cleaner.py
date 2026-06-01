from __future__ import annotations


def parse_amount(raw: str) -> float:
    text = str(raw).strip().replace(",", "")
    return float(text)
