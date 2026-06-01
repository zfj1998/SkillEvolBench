from __future__ import annotations
import json
from pathlib import Path
from claim_loader import load_claims
from contradiction_policy import classify_pair

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    graph = load_claims()
    claims = {claim["id"]: claim for claim in graph["claims"]}
    results = []
    for pair in graph["candidate_pairs"]:
        result = classify_pair(pair, claims)
        results.append({
            "pair_id": pair["id"],
            "left": pair["left"],
            "right": pair["right"],
            "label": result["label"],
            "type": result["type"],
            "reason": result["reason"],
            "evidence": [claims[pair["left"]]["quote"], claims[pair["right"]]["quote"]],
        })
    report = {
        "checked_pairs": len(results),
        "contradictions": [item for item in results if item["label"] == "contradiction"],
        "non_contradictions": [item for item in results if item["label"] != "contradiction"],
        "results": results,
    }
    (OUTPUT / "consistency_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
