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
(PROJECT_ROOT / "dimension_discovery.py").write_text(r"""
from __future__ import annotations
from collections import defaultdict

def discover_dimensions(sources):
    grouped = defaultdict(list)
    for source in sources:
        for dimension in source.get("dimensions", []):
            name = str(dimension).replace("_", " ")
            grouped[name].append(f"{source['id']}: {source.get('notes', '')}")
    priority = ["cost", "security", "complexity", "scalability", "portability", "operational simplicity", "reliability"]
    result = []
    for name in priority:
        evidence = grouped.get(name) or grouped.get(name.replace(" ", "_"))
        if evidence:
            result.append({"name": name, "evidence": evidence[:3], "comparison": "; ".join(evidence[:2])})
    for name, evidence in grouped.items():
        if len(result) >= 6:
            break
        if not any(item["name"] == name for item in result):
            result.append({"name": name, "evidence": evidence[:3], "comparison": "; ".join(evidence[:2])})
    return result
""", encoding="utf-8")
PYCODE
