from __future__ import annotations

import json
from pathlib import Path


def write_payload(path: str | Path, payload: dict[str, object]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding='utf-8')
