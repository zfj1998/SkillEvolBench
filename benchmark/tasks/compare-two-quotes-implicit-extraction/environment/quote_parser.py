from __future__ import annotations

import re


def grab(text: str, pattern: str, default=None):
    match = re.search(pattern, text, re.I)
    return match.group(1).strip() if match else default


def parse_quote_text(text: str, supplier: str) -> dict:
    qty = int(grab(text, r"Qty:\s*(\d+)"))
    unit_price = float(grab(text, r"Unit Price:\s*\$(\d+(?:\.\d+)?)"))
    quoted_total = float(
        grab(text, r"Quoted Total(?: \(excluding shipping\))?:\s*\$(\d+(?:,\d{3})*(?:\.\d+)?)").replace(",", "")
    )
    shipping_match = grab(text, r"(?:Shipping|Freight)(?: fee)?(?: of)?\s*\$?(\d+(?:,\d{3})*(?:\.\d+)?)", "0")
    shipping = shipping_match.replace(",", "")
    return {
        "supplier": supplier,
        "item": grab(text, r"Item:\s*([^\n]+)"),
        "qty": qty,
        "unit_price": unit_price,
        "quoted_total": quoted_total,
        "shipping": float(shipping),
        "warranty": grab(text, r"Warranty:\s*([^\n]+)"),
        "delivery": grab(text, r"Delivery:\s*([^\n]+)"),
    }
