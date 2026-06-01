from __future__ import annotations
import json
from pathlib import Path
from source_loader import load_sources
from dimension_discovery import discover_dimensions

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    dims = discover_dimensions(load_sources())
    result = {"dimensions": dims, "recommendation": "kubernetes", "rationale": "Better for scale."}
    (OUTPUT / "evaluation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
