from __future__ import annotations


TITLE_ALIASES = {
    "ops manager": "Operations Manager",
    "operations mgr": "Operations Manager",
    "operations manager": "Operations Manager",
    "customer success lead": "Customer Success Lead",
}


def normalize_title(title: str) -> str:
    if not title:
        return ""
    key = " ".join(title.lower().split())
    return TITLE_ALIASES.get(key, title)
