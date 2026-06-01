from __future__ import annotations

def is_relevant(source: dict) -> bool:
    tags = {t.lower() for t in source.get("tags", [])}
    return bool(tags & {"energy", "renewables", "solar", "wind", "hydrogen", "policy"})
