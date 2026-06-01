from __future__ import annotations

import json
from pathlib import Path


def write_evidence(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"items": items}, indent=2), encoding="utf-8")
