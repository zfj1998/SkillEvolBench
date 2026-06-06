#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

cat > "$PROJECT_ROOT/scope_normalizer.py" <<'PY'
from __future__ import annotations


def same_context(left: dict, right: dict) -> bool:
    keys = ["entity", "metric", "period", "scope"]
    return all(left.get(key) == right.get(key) for key in keys)


def relation(left: dict, right: dict) -> str:
    if left.get("period") != right.get("period"):
        if {left.get("period"), right.get("period")} == {"short_term", "long_term"}:
            return "different_time_scale"
        return "different_timeframe"
    if left.get("scope") != right.get("scope"):
        return "different_scope"
    return "same_context"
PY

cat > "$PROJECT_ROOT/contradiction_policy.py" <<'PY'
from __future__ import annotations

from scope_normalizer import relation, same_context


def classify_pair(pair: dict, claims: dict[str, dict]) -> dict:
    left = claims[pair["left"]]
    right = claims[pair["right"]]
    context_relation = relation(left, right)

    if context_relation != "same_context":
        return {
            "label": "not_contradiction",
            "type": context_relation,
            "reason": f"{left.get('period')} / {left.get('scope')} and {right.get('period')} / {right.get('scope')} are different contexts, not a direct conflict.",
        }

    if same_context(left, right) and left.get("polarity") and right.get("polarity") and left.get("polarity") != right.get("polarity"):
        return {
            "label": "contradiction",
            "type": "explicit",
            "reason": "Same entity, metric, period, and scope but one claim affirms the point while the other denies it.",
        }

    if same_context(left, right) and left.get("value") != right.get("value"):
        return {
            "label": "contradiction",
            "type": "explicit",
            "reason": "Same entity, metric, period, and scope but incompatible values are reported.",
        }

    return {
        "label": "not_contradiction",
        "type": "compatible",
        "reason": "The claims do not contain an incompatible same-context value or polarity.",
    }
PY

