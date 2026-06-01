from __future__ import annotations

import json
from pathlib import Path


def write_audit(path: Path, resolved_labels: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"resolved_labels": resolved_labels}, indent=2), encoding="utf-8")
