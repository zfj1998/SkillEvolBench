from __future__ import annotations

NULL_MARKERS = {"", "n/a", "null", "-"}


def parse_revenue(raw: str) -> float | None:
    text = str(raw).strip()
    if text.lower() in NULL_MARKERS:
        return None
    text = text.replace("$", "")
    return float(text)
