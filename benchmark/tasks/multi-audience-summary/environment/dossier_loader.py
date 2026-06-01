from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_dossier() -> dict:
    return json.loads((ROOT / "dossier.json").read_text(encoding="utf-8"))
