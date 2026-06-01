from __future__ import annotations


def classify_change(old: str, new: str) -> str:
    if old and new:
        return "modified"
    if old and not new:
        return "deleted"
    return "added"
