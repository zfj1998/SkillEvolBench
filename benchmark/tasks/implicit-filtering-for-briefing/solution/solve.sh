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
"topic_filter.py": r"""
from __future__ import annotations

def is_relevant(source: dict) -> bool:
    tags = {str(tag).lower() for tag in source.get("tags", [])}
    renewable_topics = {"renewables", "solar", "wind", "hydrogen", "biofuels", "capacity", "electricity share", "generation", "policy", "tripling pledge"}
    noise_topics = {"semiconductors", "ai", "ai chips", "investment"}
    return bool(tags & renewable_topics) and not bool(tags & noise_topics)
""",
"briefing_pipeline.py": r"""
from __future__ import annotations
from pathlib import Path
from source_loader import load_sources
from topic_filter import is_relevant

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def tags(source: dict) -> set[str]:
    return {str(tag).lower() for tag in source.get("tags", [])}

def bullet(source: dict) -> str:
    return f"- {source['id']} ({source['title']}): {source.get('notes', '')}"

def main():
    picked = [source for source in load_sources() if is_relevant(source)]
    trend_sources = [s for s in picked if tags(s) & {"solar", "wind", "hydrogen", "biofuels", "generation", "capacity", "electricity share"}]
    challenge_sources = [s for s in picked if tags(s) & {"policy", "tripling pledge"} or "gap" in s.get("notes", "").lower()]
    outlook_sources = [s for s in picked if s not in trend_sources[:3] and s not in challenge_sources[:2]]
    if not outlook_sources:
        outlook_sources = picked[-2:]
    lines = ["# Renewable Energy Briefing", "", "## Trends"]
    for source in trend_sources[:4]:
        lines.append(bullet(source))
    lines.extend(["", "## Challenges"])
    for source in challenge_sources[:3]:
        lines.append(bullet(source))
    lines.extend(["", "## Outlook"])
    for source in outlook_sources[:3]:
        lines.append(bullet(source))
    lines.extend(["", "## Sources Used"])
    for source in picked:
        lines.append(f"- {source['id']}: {source['title']}")
    (OUTPUT / "briefing.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
"""
}
for name, content in files.items():
    (PROJECT_ROOT / name).write_text(content, encoding="utf-8")
PYCODE
