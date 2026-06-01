from __future__ import annotations
from dimension_weights import WEIGHTS

def score(source: dict) -> float:
    tags = {t.lower() for t in source.get("tags", [])}
    relevance = 1.0 if "ai" in tags else 0.4
    if "medical diagnosis" in tags:
        relevance += 0.3
    evidence = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(source.get("evidence_strength"), 0.2)
    recency = max(0.1, min(1.0, (source["year"] - 2015) / 10))
    return relevance * WEIGHTS["relevance"] + evidence * WEIGHTS["evidence"] + recency * WEIGHTS["recency"]
