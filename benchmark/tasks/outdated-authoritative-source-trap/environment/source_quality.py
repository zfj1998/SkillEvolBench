from __future__ import annotations

TYPE_WEIGHT = {
    "peer_reviewed_study": 5,
    "randomized_controlled_trial": 5,
    "regulatory_reference": 4,
    "research_report": 4,
    "official_report": 4,
    "market_forecast": 3,
    "industry_survey": 3,
    "policy_report": 3,
    "vendor_documentation": 2,
    "opinion": 1,
    "blog": 1,
}

STRENGTH_WEIGHT = {"high": 3, "medium": 2, "low": 1, "unknown": 0, None: 0}

def quality_score(source: dict, *, current_year: int = 2026) -> float:
    source_type = source.get("source_type", "unknown")
    strength = source.get("evidence_strength", "unknown")
    year = int(source.get("year") or current_year)
    recency = max(0, 5 - max(0, current_year - year))
    return TYPE_WEIGHT.get(source_type, 1) + STRENGTH_WEIGHT.get(strength, 0) + recency / 5

def is_current(source: dict, *, min_year: int = 2023) -> bool:
    return int(source.get("year") or 0) >= min_year
