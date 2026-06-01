from __future__ import annotations

def classify_citation(citation: dict, source: dict | None) -> dict:
    if source is None:
        return {"label": "invalid", "checks": ["existence"], "reason": "source id missing from local registry"}
    doi = source.get("doi") or ""
    if doi and "." not in doi:
        return {"label": "fake", "checks": ["format"], "reason": "malformed DOI"}
    return {"label": "valid", "checks": ["existence"], "reason": "source exists in local registry"}
