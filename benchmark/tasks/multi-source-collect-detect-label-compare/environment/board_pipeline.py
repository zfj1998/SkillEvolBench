from __future__ import annotations
import json
from pathlib import Path
from source_loader import load_sources
from label_audit import label_source

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    sources = load_sources()
    labels = [{"source_id": s["id"], "label": label_source(s)} for s in sources]
    decision = {"winner": "salesforce", "basis": "majority of independent sources"}
    (OUTPUT / "board_report.json").write_text(json.dumps({"labels": labels, "decision": decision}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
