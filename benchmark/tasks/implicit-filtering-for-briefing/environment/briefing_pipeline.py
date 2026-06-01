from __future__ import annotations
from pathlib import Path
from source_loader import load_sources
from topic_filter import is_relevant

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    picked = [s for s in load_sources() if is_relevant(s)]
    lines = ["# Renewable Energy Briefing", "", "## Trends"]
    for src in picked[:5]:
        lines.append(f"- {src['title']}: {src['notes']}")
    (OUTPUT / "briefing.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
