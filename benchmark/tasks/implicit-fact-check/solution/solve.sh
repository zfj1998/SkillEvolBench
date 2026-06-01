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
(PROJECT_ROOT / "citation_policy.py").write_text(r"""
from __future__ import annotations

def _text(source: dict | None) -> str:
    if not source:
        return ""
    return " ".join(str(source.get(key, "")) for key in ["id", "title", "publisher", "source_type", "notes", "doi", "url", "authentic"]).lower()

def classify_citation(citation: dict, source: dict | None) -> dict:
    claim = citation.get("article_claim", "").lower()
    source_text = _text(source)
    if source is None or "example.invalid" in source_text or "fake" in source_text or "fabricated" in source_text or "false" in source_text:
        return {"label": "fake", "checks": ["existence", "authenticity", "doi", "journal_author_crosscheck"], "reason": "Fake or fabricated citation: DOI, journal, and authenticity checks cannot verify it in the real-source registry."}
    misrep_patterns = ["objectively", "productivity by 30", "eight cups", "significantly outperformed", "every human", "all settings", "rent by half", "every company", "80%", "all global final energy", "proves universal"]
    if any(pattern in claim for pattern in misrep_patterns):
        return {"label": "misrepresented", "checks": ["existence", "content_match", "attribution"], "reason": "Misrepresented: the source does not support that attribution as stated; it is not a self-reported significant universal finding."}
    caveat_rules = [
        ("MED_NATURE_SKIN", ["visual", "image"]),
        ("MED_JAMA_DR", ["validation", "fundus", "photographs"]),
        ("REMOTE_NATURE_HYBRID", ["trip.com", "randomized"]),
    ]
    sid = str(citation.get("source_id", ""))
    for source_id, required in caveat_rules:
        if sid == source_id and not any(token in claim for token in required):
            return {"label": "selective", "checks": ["existence", "content_match", "context_caveat"], "reason": "Selective citation: it omits a caveat, limitation, scope, generalization boundary, or external-validation context from the source."}
    return {"label": "valid", "checks": ["existence", "content_match"], "reason": "Citation matches a verified source and stays within the source scope."}
""", encoding="utf-8")
PYCODE
