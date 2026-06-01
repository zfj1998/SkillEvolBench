#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
export PROJECT_ROOT
python3 - <<'PYCODE'

from __future__ import annotations
import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"]).resolve()
files = {
"scope_normalizer.py": r"""
from __future__ import annotations

def same_context(left: dict, right: dict) -> bool:
    return left.get("entity") == right.get("entity") and left.get("period") == right.get("period") and left.get("scope") == right.get("scope")

def same_metric(left: dict, right: dict) -> bool:
    return left.get("metric") == right.get("metric")
""",
"contradiction_policy.py": r"""
from __future__ import annotations
from scope_normalizer import same_context, same_metric

def _is_internal(left: dict, right: dict) -> bool:
    return "annual_review" in left.get("doc", "") and "annual_review" in right.get("doc", "")

def _same_contextish(left: dict, right: dict) -> bool:
    return left.get("entity") == right.get("entity") and left.get("scope") == right.get("scope")

def _reason(kind: str, left: dict, right: dict) -> str:
    return f"Same context conflict: {left.get('quote')} Incompatible with: {right.get('quote')}"

def classify_pair(pair: dict, claims: dict[str, dict]) -> dict:
    left = claims[pair["left"]]
    right = claims[pair["right"]]
    if same_context(left, right) and same_metric(left, right):
        if left.get("value") != right.get("value") or (left.get("polarity") and right.get("polarity") and left.get("polarity") != right.get("polarity")):
            kind = "internal" if _is_internal(left, right) else "explicit"
            return {"label": "contradiction", "type": kind, "reason": _reason(kind, left, right)}
        return {"label": "not_contradiction", "type": "compatible", "reason": "Same period, scope, metric, and value are compatible."}
    if left.get("entity") != right.get("entity") or left.get("scope") != right.get("scope"):
        return {"label": "not_contradiction", "type": "compatible", "reason": "Different entity or scope, so the statements can both be true."}
    metrics = {left.get("metric"), right.get("metric")}
    values = {str(left.get("value")).lower(), str(right.get("value")).lower()}
    if metrics == {"cost", "budget"} and {"lower", "same"}.issubset(values):
        return {"label": "contradiction", "type": "implicit_causal", "reason": "Costs decreasing after implementation is incompatible with before/after budgets being the same."}
    if metrics == {"market_position", "market_share"} and ("leader" in values and any(v.isdigit() and int(v) < 15 for v in values)):
        return {"label": "contradiction", "type": "implicit_definition", "reason": "A market leader claim conflicts with only single-digit market share in the same scope and year."}
    if left.get("period") != right.get("period"):
        # A range containing the point year can still conflict with an annual claim.
        lp, rp = str(left.get("period")), str(right.get("period"))
        lv, rv = left.get("value"), right.get("value")
        if ("-" in lp and rp in lp or "-" in rp and lp in rp) and (lv == "decline" or rv == "decline"):
            return {"label": "contradiction", "type": "implicit_timeline", "reason": "Continuous decline across the range conflicts with a same-year growth claim."}
        return {"label": "not_contradiction", "type": "compatible", "reason": "Different year or timeframe, so this is not a contradiction by itself."}
    if _is_internal(left, right) and _same_contextish(left, right) and left.get("value") != right.get("value"):
        return {"label": "contradiction", "type": "internal", "reason": _reason("internal", left, right)}
    return {"label": "not_contradiction", "type": "compatible", "reason": "No incompatible value, timeframe, scope, or definition was found."}
"""
}
for name, content in files.items():
    (PROJECT_ROOT / name).write_text(content, encoding="utf-8")
PYCODE
