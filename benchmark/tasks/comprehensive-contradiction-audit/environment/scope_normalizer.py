from __future__ import annotations

def same_context(left: dict, right: dict) -> bool:
    # Legacy matcher only checks the coarse topic.
    return left.get("entity") == right.get("entity") and left.get("metric") == right.get("metric")
