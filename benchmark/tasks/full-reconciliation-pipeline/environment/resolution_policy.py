from __future__ import annotations

from source_priority import PRIORITY


def choose_value(field_name: str, candidates: list[tuple[str, object]]):
    ranked = sorted(candidates, key=lambda item: PRIORITY.get(item[0], 99))
    for source, value in ranked:
        if value not in ("", None, {}):
            return value, source
    return ranked[0][1] if ranked else None, ranked[0][0] if ranked else ""
