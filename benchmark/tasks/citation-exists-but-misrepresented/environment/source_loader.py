from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_sources() -> dict[str, dict]:
    sources = json.loads((ROOT / "source_manifest.json").read_text(encoding="utf-8"))
    return {source["id"]: source for source in sources}

def load_citations() -> list[dict]:
    return json.loads((ROOT / "citation_packet.json").read_text(encoding="utf-8"))
