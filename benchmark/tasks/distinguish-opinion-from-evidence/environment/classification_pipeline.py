from __future__ import annotations
import json
from pathlib import Path
from source_loader import load_sources
from evidence_policy import classify

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    labels = []
    selected = []
    for source in load_sources():
        label, reason = classify(source)
        labels.append({"source_id": source["id"], "label": label, "reason": reason})
        if label == "evidence":
            selected.append(source["id"])
    result = {"labels": labels, "selected_priority": selected[:7]}
    (OUTPUT / "classification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
