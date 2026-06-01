from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

CLAIMS = json.loads((ROOT / "claim_packets.json").read_text())

def classify(claim: str) -> str:
    return "misleading" if "%" in claim else "accurate"

def main():
    reviews = []
    for item in CLAIMS["claims"]:
        reviews.append({"id": item["id"], "label": classify(item["claim"]), "correction": "Needs more context."})
    (OUTPUT / "claim_review.json").write_text(json.dumps({"reviews": reviews}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
