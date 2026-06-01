from __future__ import annotations

import re


def canonical_city(value: str) -> str:
    normalized = str(value).replace("\u00a0", " ").strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    alias_map = {
        "ny": "new york",
        "nyc": "new york",
        "la": "los angeles",
    }
    return alias_map.get(normalized, normalized)
