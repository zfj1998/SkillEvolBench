from __future__ import annotations

import re


def extract_claims(text: str) -> dict[str, str]:
    matches = re.findall(r"(?ms)^##\s+(\d+\.\s+[^\n]+)\n\n(.*?)(?=^##\s+\d+\.|\Z)", text)
    return {title.strip(): body.strip() for title, body in matches}
