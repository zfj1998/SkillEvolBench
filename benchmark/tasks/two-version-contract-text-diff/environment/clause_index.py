from __future__ import annotations

import re


def split_sections(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?m)^##\s+", text)
    sections = []
    for part in parts[1:]:
        title, _, body = part.partition("\n")
        sections.append((title.strip(), body.strip()))
    return sections
