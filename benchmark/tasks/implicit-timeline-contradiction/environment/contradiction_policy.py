from __future__ import annotations
from scope_normalizer import same_context

def classify_pair(pair: dict, claims: dict[str, dict]) -> dict:
    left = claims[pair["left"]]
    right = claims[pair["right"]]
    if not same_context(left, right):
        return {"label": "not_contradiction", "type": "compatible", "reason": "different entity or metric"}
    if left.get("polarity") and right.get("polarity") and left.get("polarity") != right.get("polarity"):
        return {"label": "contradiction", "type": "explicit", "reason": "opposite polarity"}
    return {"label": "not_contradiction", "type": "unchecked", "reason": "no explicit negation found"}
