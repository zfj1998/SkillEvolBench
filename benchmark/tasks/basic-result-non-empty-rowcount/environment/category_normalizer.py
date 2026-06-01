from __future__ import annotations


def normalize_category(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = " ".join(text.split())
    return text
