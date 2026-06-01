from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_manifest() -> list[dict]:
    return json.loads((ROOT / "source_manifest.json").read_text(encoding="utf-8"))

def source_by_id() -> dict[str, dict]:
    return {source["id"]: source for source in load_manifest()}

def urls_for(source_ids: list[str]) -> list[str]:
    sources = source_by_id()
    return [sources[source_id]["url"] for source_id in source_ids if source_id in sources]

def provenance_block(source_ids: list[str], method: str, limitations: list[str] | None = None) -> dict:
    return {
        "source_ids": source_ids,
        "source_urls": urls_for(source_ids),
        "method": method,
        "limitations": limitations or [],
    }
