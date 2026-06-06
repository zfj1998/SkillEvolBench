#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
import re
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))

policy = root / "relevance_policy.py"
text = policy.read_text(encoding="utf-8")
body = '''def score_source(source: dict) -> tuple[float, str]:
    tags = {t.lower() for t in source.get("tags", [])}
    notes = source.get("notes", "").lower()
    score = 0.0
    reasons = []
    if "medical diagnosis" in tags:
        score += 5.0
        reasons.append("diagnosis-focused source")
    if "clinical validation" in tags or "validation" in tags:
        score += 2.0
        reasons.append("validation evidence")
    if "screening" in tags or "devices" in tags or "healthcare" in tags:
        score += 1.0
        reasons.append("clinical or healthcare context")
    if source.get("tier") == "high":
        score += 2.0
    elif source.get("tier") == "medium":
        score += 0.5
    elif source.get("tier") in {"low", "irrelevant"}:
        score -= 3.0
    if source.get("source_type") in {"peer_reviewed_study", "regulatory_reference"}:
        score += 1.0
    if "not tightly focused" in notes or "off-topic" in notes or "not about ai methods" in notes:
        score -= 2.5
    return score, "; ".join(reasons) or "content-level relevance"
'''
text = re.sub(r"def score_source\(source: dict\).*", body, text, flags=re.S)
policy.write_text(text, encoding="utf-8")

pipeline = root / "search_pipeline.py"
text = pipeline.read_text(encoding="utf-8")
text = text.replace(
    '            "reason": reason,\n',
    '''            "reason": f"{reason}; {source['notes']}",\n''',
)
text = text.replace(
    '    selected = ranked[:5]\n'
    '    data = {"query": "AI in medical diagnosis", "selected": selected, "screened": len(ranked)}\n',
    '    selected = []\n'
    '    for rank, item in enumerate(ranked[:5], start=1):\n'
    '        item = dict(item)\n'
    '        item["rank"] = rank\n'
    '        selected.append(item)\n'
    '    data = {"query": "AI in medical diagnosis", "selected": selected, "screened": len(ranked)}\n',
)
pipeline.write_text(text, encoding="utf-8")
PY
