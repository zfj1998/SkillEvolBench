from __future__ import annotations

ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff")


def normalize_email(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    for char in ZERO_WIDTH:
        text = text.replace(char, "")
    text = text.strip().lower()
    if text in {"", "null", "none", "na"}:
        return None
    return text
