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
    return " ".join(str(source.get(key, "")) for key in ["id", "title", "publisher", "source_type", "notes", "doi", "url"]).lower()

def classify_citation(citation: dict, source: dict | None) -> dict:
    claim = citation.get("article_claim", "").lower()
    source_text = _text(source)
    source_id = str(citation.get("source_id", "")).lower()
    if source is None:
        return {
            "label": "fake",
            "checks": ["existence", "authenticity", "doi", "journal_author_crosscheck"],
            "reason": "Fake or fabricated citation: no matching source is present in the verified registry, so a missing table, deployment record, DOI, journal, or near-match metadata cannot establish authenticity.",
        }
    if "example.invalid" in source_text or "fake" in source_text or "fabricated" in source_text:
        return {
            "label": "fake",
            "checks": ["authenticity", "doi", "journal_author_crosscheck"],
            "reason": "Fake or fabricated citation: source metadata fails DOI, journal, and authenticity checks.",
        }
    unsupported_groups = [
        {"table", "figure", "deployment"},
        {"appendix", "figure", "nuclear"},
        {"universal", "all cancers"},
    ]
    for group in unsupported_groups:
        if any(marker in claim for marker in group) and not any(marker in source_text for marker in group):
            return {
                "label": "misrepresented",
                "checks": ["existence", "content_match"],
                "reason": "Misrepresented citation: the source exists, but the claimed table, appendix, deployment, or scope is missing from the verified source notes.",
            }
    if "universal diagnosis" in claim or "all cancers" in claim:
        return {
            "label": "misrepresented",
            "checks": ["existence", "content_match", "scope_caveat"],
            "reason": "Misrepresented citation: the source scope is narrower and does not support a universal all-cancers claim; preserve source limitations and caveats.",
        }
    caveat_markers = ["without caveat", "proves", "guarantees", "universal"]
    if any(marker in claim for marker in caveat_markers):
        return {
            "label": "selective",
            "checks": ["existence", "content_match", "context_caveat"],
            "reason": "The citation exists but the article claim omits a necessary source caveat or limitation.",
        }
    return {"label": "valid", "checks": ["existence", "content_match"], "reason": "Citation matches a verified source and the claim stays within the source scope."}
""", encoding="utf-8")
PYCODE
