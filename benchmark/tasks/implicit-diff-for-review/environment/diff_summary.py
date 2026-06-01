from __future__ import annotations

import re


def extract_sections(text: str) -> dict[str, str]:
    matches = re.findall(r"(?ms)^##\s+([^\n]+)\n\n(.*?)(?=^##\s+|\Z)", text)
    return {title.strip(): body.strip() for title, body in matches}
