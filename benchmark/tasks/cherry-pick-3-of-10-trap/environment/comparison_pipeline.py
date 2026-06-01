from __future__ import annotations
import json
from pathlib import Path
from cherry_pick_guard import select_dimensions

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

ALL_DIMENSIONS = ["pricing", "security", "integrations", "usability", "support", "compliance", "governance", "implementation"]

def main():
    chosen = select_dimensions(ALL_DIMENSIONS)
    (OUTPUT / "comparison_summary.json").write_text(json.dumps({"dimensions_used": chosen}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
