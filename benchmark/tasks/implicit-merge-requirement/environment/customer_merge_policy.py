from __future__ import annotations


def choose_name(existing: str, incoming: str) -> str:
    existing = (existing or "").strip()
    incoming = (incoming or "").strip()
    if len(incoming) > len(existing):
        return incoming
    return existing or incoming


def merge_customer(existing: dict | None, incoming: dict) -> dict:
    if existing is None:
        merged = dict(incoming)
        merged["_sources"] = [incoming["source"]]
        return merged

    merged = dict(existing)
    merged["name"] = choose_name(existing.get("name", ""), incoming.get("name", ""))
    for field in ("phone", "city", "company", "tag"):
        if not merged.get(field) and incoming.get(field):
            merged[field] = incoming[field]
    merged["_sources"] = sorted(set(existing["_sources"] + [incoming["source"]]))
    return merged
