from __future__ import annotations

import re


def referenced_page(text: str) -> str | None:
    match = re.search(r"page\s+(\d+)", text, flags=re.IGNORECASE)
    return match.group(1) if match else None
