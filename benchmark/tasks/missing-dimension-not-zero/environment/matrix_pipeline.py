from __future__ import annotations
import json
from pathlib import Path
from source_loader import load_sources
from missingness_policy import normalize

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    rows = [
        {"dimension": "security", "salesforce": "documented", "hubspot": normalize(None)},
        {"dimension": "marketplace_scale", "salesforce": "documented", "hubspot": "documented"},
        {"dimension": "fedramp", "salesforce": "documented", "hubspot": normalize(None)},
    ]
    (OUTPUT / "comparison_matrix.json").write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
