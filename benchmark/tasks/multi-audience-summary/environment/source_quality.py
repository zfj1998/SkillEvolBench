from __future__ import annotations

TYPE_WEIGHT = {
    "peer_reviewed_study": 5,
    "randomized_controlled_trial": 5,
    "official_report": 4,
    "regulatory_reference": 4,
    "energy_report": 4,
    "research_report": 4,
    "market_forecast": 3,
    "policy_report": 3,
    "vendor_documentation": 2,
    "opinion": 1,
}

def quality_score(source: dict, *, current_year: int = 2026) -> float:
    year = int(source.get("year") or current_year)
    recency = max(0, 5 - max(0, current_year - year))
    return TYPE_WEIGHT.get(source.get("source_type", "unknown"), 1) + recency / 5
