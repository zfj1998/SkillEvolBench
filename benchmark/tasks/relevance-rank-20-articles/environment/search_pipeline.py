from __future__ import annotations
import json
from pathlib import Path
from source_loader import load_sources
from relevance_policy import score_source

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    ranked = []
    for source in load_sources():
        score, reason = score_source(source)
        ranked.append({
            "source_id": source["id"],
            "title": source["title"],
            "score": round(score, 2),
            "reason": reason,
        })
    ranked.sort(key=lambda item: (-item["score"], item["source_id"]))
    selected = ranked[:5]
    data = {"query": "AI in medical diagnosis", "selected": selected, "screened": len(ranked)}
    (OUTPUT / "ranking.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
