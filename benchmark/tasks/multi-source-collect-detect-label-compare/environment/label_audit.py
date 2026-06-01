from __future__ import annotations
def label_source(source: dict) -> str:
    if source["source_type"].startswith("vendor"):
        return "independent"
    if source["source_type"] == "independent_review":
        return "independent"
    return "unknown"
