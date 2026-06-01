from __future__ import annotations

def score_source(source: dict) -> tuple[float, str]:
    title = source["title"].lower()
    tags = [t.lower() for t in source.get("tags", [])]
    score = 0.0
    reasons = []
    if "ai" in title or "artificial intelligence" in title or "deep learning" in title:
        score += 3.0
        reasons.append("title mentions AI")
    if "diagnosis" in title or "screening" in title:
        score += 2.0
        reasons.append("title mentions diagnosis/screening")
    if source.get("evidence_strength") == "high":
        score += 1.0
    score += min(source["year"] - 2015, 10) * 0.05
    score += 0.2 * len(tags)
    return score, "; ".join(reasons) or "keyword overlap"
