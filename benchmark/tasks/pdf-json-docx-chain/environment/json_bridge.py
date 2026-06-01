from __future__ import annotations

import json


def write_json(path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
