from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_claims() -> dict:
    return json.loads((ROOT / "claim_graph.json").read_text(encoding="utf-8"))
