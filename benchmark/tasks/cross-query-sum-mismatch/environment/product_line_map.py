from __future__ import annotations

import re

ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff")
CANONICAL_MAP = {
    "software": "Software",
    "sw": "Software",
    "soft ware": "Software",
    "hardware": "Hardware",
    "hw": "Hardware",
    "hard ware": "Hardware",
    "services": "Services",
    "service": "Services",
    "svc": "Services",
    "consulting": "Consulting",
    "consult": "Consulting",
    "advisory": "Consulting",
}


def canonicalize_product_line(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    for char in ZERO_WIDTH:
        text = text.replace(char, "")
    text = re.sub(r"\s+", " ", text.strip().lower())
    return CANONICAL_MAP.get(text)
