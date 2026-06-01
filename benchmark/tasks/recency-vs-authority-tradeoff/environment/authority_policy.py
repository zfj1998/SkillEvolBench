from __future__ import annotations

def source_score(source: dict) -> float:
    score = 0.0
    if source["publisher"] in {"Stanford HAI", "Gartner"}:
        score += 4
    if source["source_type"] in {"research_report", "research_summary"}:
        score += 2
    score += max(0, 2025 - source["year"]) * -0.1
    return score
