from __future__ import annotations


def normalize_value(field: str, value: str) -> str:
    cleaned = value.strip()
    if field == "salary":
        return cleaned.replace("$", "").replace(",", "")
    return cleaned
