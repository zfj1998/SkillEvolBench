from __future__ import annotations

def rank_sections(sections: list[dict]) -> list[dict]:
    # Legacy editorial flow preserves document order, which overweights background sections.
    return sorted(sections, key=lambda section: section.get("order", 999))
