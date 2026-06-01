from __future__ import annotations

import re

from city_aliases import CITY_ALIASES


def _basic_normalize(value: str) -> str:
    cleaned = (
        str(value)
        .replace("\u00a0", " ")
        .replace("\u200b", "")
        .replace("’", " ")
        .replace(".", " ")
        .replace("-", " ")
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def canonical_city_name(value: str) -> str:
    normalized = _basic_normalize(value)
    return CITY_ALIASES.get(normalized, normalized)
