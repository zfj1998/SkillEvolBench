#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

cat > "$PROJECT_ROOT/scope_normalizer.py" <<'PY'
from __future__ import annotations


def same_context(left: dict, right: dict) -> bool:
    keys = ["entity", "period", "scope"]
    return all(left.get(key) == right.get(key) for key in keys)


def period_contains(period: str | None, year: str | None) -> bool:
    if not period or not year:
        return False
    if period == year:
        return True
    if "-" in period and year.isdigit():
        start, end = period.split("-", 1)
        return start.isdigit() and end.isdigit() and int(start) <= int(year) <= int(end)
    return False
PY

cat > "$PROJECT_ROOT/contradiction_policy.py" <<'PY'
from __future__ import annotations

from scope_normalizer import period_contains


def classify_pair(pair: dict, claims: dict[str, dict]) -> dict:
    left = claims[pair["left"]]
    right = claims[pair["right"]]
    claims_pair = [left, right]
    metrics = {claim.get("metric") for claim in claims_pair}
    values = {str(claim.get("value")).lower() for claim in claims_pair}

    growth = next((claim for claim in claims_pair if claim.get("metric") == "growth"), None)
    trend = next((claim for claim in claims_pair if claim.get("metric") == "trend"), None)
    if growth and trend and growth.get("value", 0) > 0 and str(trend.get("value")).lower() == "decline" and period_contains(trend.get("period"), growth.get("period")):
        return {
            "label": "contradiction",
            "type": "implicit_timeline",
            "reason": "A continuous decline through the specific year is incompatible with positive growth in that same year.",
        }

    if metrics == {"cost", "budget"} and {"lower", "same"}.issubset(values):
        return {
            "label": "contradiction",
            "type": "implicit_causal",
            "reason": "A cost decrease after implementation conflicts with an unchanged before/after operating budget.",
        }

    if {"market_position", "market_share"}.issubset(metrics):
        share = next((claim.get("value") for claim in claims_pair if claim.get("metric") == "market_share"), None)
        position = next((claim.get("value") for claim in claims_pair if claim.get("metric") == "market_position"), "")
        if str(position).lower() == "leader" and isinstance(share, (int, float)) and share <= 10:
            return {
                "label": "contradiction",
                "type": "implicit_definition",
                "reason": "Calling a vendor the market leader is inconsistent with only a small market share in the same market.",
            }

    return {
        "label": "not_contradiction",
        "type": "compatible",
        "reason": "The claims concern compatible or different metrics and do not imply an inconsistency.",
    }
PY

