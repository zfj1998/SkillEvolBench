from __future__ import annotations
import json
from pathlib import Path
from source_loader import load_sources
from authority_policy import choose_best

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    chosen = choose_best(load_sources())
    data = {
        "topic": "global AI investment",
        "selected_source": chosen["id"],
        "estimate": chosen["notes"],
        "rationale": f"Selected the most authoritative source: {chosen['publisher']}.",
    }
    (OUTPUT / "investment_estimate.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
