from __future__ import annotations
import json
from pathlib import Path
from source_loader import load_sources
from authority_policy import source_score

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    sources = sorted(load_sources(), key=source_score, reverse=True)
    chosen = sources[0]
    data = {
        "topic": "current AI chip market size",
        "selected_source": chosen["id"],
        "estimate": chosen["notes"],
        "reasoning": f"Selected {chosen['publisher']} because it is authoritative.",
    }
    (OUTPUT / "market_estimate.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
