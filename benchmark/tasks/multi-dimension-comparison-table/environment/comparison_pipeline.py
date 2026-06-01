from __future__ import annotations
import json
from pathlib import Path
from source_loader import load_sources
from dimension_registry import DIMENSIONS

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    sources = load_sources()
    rows = []
    for dim in DIMENSIONS[:4]:
        matches = [s["id"] for s in sources if dim in s.get("dimensions", [])][:1]
        rows.append({"dimension": dim, "sources": matches, "comparison": "partial"})
    (OUTPUT / "comparison.json").write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
