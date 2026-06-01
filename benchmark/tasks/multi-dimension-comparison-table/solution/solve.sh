#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

cat > "$PROJECT_ROOT/dimension_registry.py" <<'PYMOD'
from __future__ import annotations

DIMENSIONS = [
    "pricing",
    "security",
    "integrations",
    "usability",
    "support",
    "compliance",
    "governance",
    "implementation",
]
PYMOD

cat > "$PROJECT_ROOT/comparison_pipeline.py" <<'PYMOD'
from __future__ import annotations

import json
from pathlib import Path

from dimension_registry import DIMENSIONS
from source_loader import load_sources

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)


def _notes_for(sources, vendor: str, dimension: str) -> list[str]:
    return [
        source["notes"]
        for source in sources
        if source.get("vendor") == vendor and dimension in source.get("dimensions", [])
    ]


def _winner(salesforce_notes: list[str], hubspot_notes: list[str], dimension: str) -> str:
    if salesforce_notes and hubspot_notes:
        if dimension in {"usability", "support"}:
            return "hubspot"
        if dimension in {"security", "compliance", "governance"}:
            return "salesforce"
        return "tie"
    if salesforce_notes:
        return "salesforce"
    if hubspot_notes:
        return "hubspot"
    return "insufficient_evidence"


def main():
    sources = load_sources()
    rows = []
    for dimension in DIMENSIONS:
        matches = [source for source in sources if dimension in source.get("dimensions", [])]
        if not matches:
            continue
        salesforce_notes = _notes_for(sources, "salesforce", dimension)
        hubspot_notes = _notes_for(sources, "hubspot", dimension)
        rows.append(
            {
                "dimension": dimension,
                "sources": [source["id"] for source in matches[:3]],
                "crm_a": salesforce_notes[0] if salesforce_notes else "insufficient evidence for Salesforce in the provided sources",
                "crm_b": hubspot_notes[0] if hubspot_notes else "insufficient evidence for HubSpot in the provided sources",
                "winner": _winner(salesforce_notes, hubspot_notes, dimension),
            }
        )

    (OUTPUT / "comparison.json").write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
    lines = ["# Comparison Table", ""]
    for row in rows:
        lines.append(f"- {row['dimension']}: {row['winner']} supported by {', '.join(row['sources'])}")
    (OUTPUT / "comparison_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
PYMOD
