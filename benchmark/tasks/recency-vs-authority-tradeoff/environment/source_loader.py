from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
def load_sources():
    return json.loads((ROOT / "source_manifest.json").read_text(encoding="utf-8"))
