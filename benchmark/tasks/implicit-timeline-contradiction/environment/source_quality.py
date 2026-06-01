from __future__ import annotations

TYPE_WEIGHT = {
    "randomized_controlled_trial": 5,
    "research_report": 4,
    "energy_report": 4,
    "market_forecast": 3,
    "official_report": 4,
}

def quality_score(source: dict, *, current_year: int = 2026) -> float:
    year = int(source.get("year") or current_year)
    recency = max(0, 5 - max(0, current_year - year))
    return TYPE_WEIGHT.get(source.get("source_type", "unknown"), 1) + recency / 5
