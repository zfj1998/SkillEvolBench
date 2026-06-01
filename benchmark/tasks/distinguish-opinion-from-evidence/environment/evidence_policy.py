from __future__ import annotations

def classify(source: dict) -> tuple[str, str]:
    text = f"{source['title']} {source['notes']}".lower()
    if any(token in text for token in ["survey", "study", "research", "data", "2024", "2025", "productivity rose", "sample", "randomized"]):
        return "evidence", "contains numbers or study-like language"
    return "opinion", "no explicit numeric evidence"
