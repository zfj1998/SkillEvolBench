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
MODE = "ceo"

priority_policy = """
from __future__ import annotations

def rank_sections(sections: list[dict]) -> list[dict]:
    return sorted(
        sections,
        key=lambda section: (-int(section.get("priority", 0)), int(section.get("order", 999))),
    )
"""

audience_policy = """
from __future__ import annotations

def audience_focus(audience: str) -> set[str]:
    mapping = {
        "technical": {"technical", "architecture", "performance", "implementation"},
        "management": {"management", "roi", "risk", "timeline", "resources"},
        "client": {"client", "user_value", "launch", "workflow"},
        "ceo": {"management", "roi", "risk", "launch", "client"},
    }
    return mapping.get(audience, {"finding", "recommendation", "governance", "risk"})
"""

summarizer = """
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
from dossier_loader import load_dossier
from priority_policy import rank_sections
from audience_policy import audience_focus

MODE = "ceo"
ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def words(text: str) -> int:
    return len(text.split())

def section_tags(section: dict) -> set[str]:
    return {str(tag).lower() for tag in section.get("tags", [])}

def build_text(sections: list[dict], opener: str | None = None) -> str:
    parts = []
    if opener:
        parts.append(opener)
    parts.extend(section["summary"] for section in sections)
    return " ".join(parts)

def choose_sections(sections: list[dict], limit: int, focus: set[str] | None = None) -> list[dict]:
    ranked = rank_sections(sections)
    if focus:
        focused = [section for section in ranked if section_tags(section) & focus]
        if focused:
            ranked = focused
    selected: list[dict] = []
    for section in ranked:
        tags = section_tags(section)
        if int(section.get("priority", 0)) <= 0 or "appendix" in tags or "background" in tags:
            continue
        candidate = selected + [section]
        if words(build_text(candidate)) <= limit:
            selected.append(section)
    if not selected:
        for section in ranked:
            if words(build_text(selected + [section])) <= limit:
                selected.append(section)
    return selected

def make_summary(sections: list[dict], limit: int, focus: set[str] | None = None, opener: str | None = None) -> dict:
    selected = choose_sections(sections, limit, focus)
    text = build_text(selected, opener)
    return {"text": text, "selected_sections": [section["id"] for section in selected], "word_count": words(text)}

def summarize_single(dossier: dict) -> dict:
    if MODE == "ceo":
        opener = "For CEO review, focus on ROI, risk, and next steps: run a staged pilot before broad rollout."
        return make_summary(dossier["sections"], 500, focus=audience_focus("ceo"), opener=opener)
    return make_summary(dossier["sections"], 500)

def summarize_multi_audience(dossier: dict) -> dict:
    openers = {
        "technical": "Technical architecture and performance summary:",
        "management": "Management ROI, risk, and migration summary:",
        "client": "Client user value and launch summary:",
    }
    summaries = {}
    for audience in ["technical", "management", "client"]:
        summaries[audience] = make_summary(dossier["sections"], 300, focus=audience_focus(audience), opener=openers[audience])
    return {"summaries": summaries}

def summarize_hierarchical(dossier: dict) -> dict:
    article_summaries = []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for article in dossier["articles"]:
        article_summary = make_summary(article["sections"], 200)
        article_summary["article_id"] = article["id"]
        article_summaries.append(article_summary)
        grouped[article.get("theme", "other")].extend(article["sections"])
    group_summaries = []
    for theme in ["method", "application"]:
        if theme in grouped:
            opener = f"{theme.title()} group summary for method validation and application evidence:" if theme == "method" else f"{theme.title()} group summary for application evidence:"
            summary = make_summary(grouped[theme], 300, opener=opener)
            summary["group"] = theme
            group_summaries.append(summary)
    all_sections = [section for article in dossier["articles"] for section in article["sections"]]
    overall_opener = "Overall synthesis: method validation and governance connect to application evidence in retinal and skin use cases."
    return {"article_summaries": article_summaries, "group_summaries": group_summaries, "overall_summary": make_summary(all_sections, 500, opener=overall_opener)}

def main():
    dossier = load_dossier()
    if MODE == "hierarchical":
        result = summarize_hierarchical(dossier)
    elif MODE == "multi_audience":
        result = summarize_multi_audience(dossier)
    else:
        result = summarize_single(dossier)
    (OUTPUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
"""

(PROJECT_ROOT / "priority_policy.py").write_text(priority_policy, encoding="utf-8")
(PROJECT_ROOT / "audience_policy.py").write_text(audience_policy, encoding="utf-8")
(PROJECT_ROOT / "summarizer.py").write_text(summarizer, encoding="utf-8")
PYCODE
