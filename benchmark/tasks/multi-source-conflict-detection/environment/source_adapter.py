from __future__ import annotations

import json
from pathlib import Path


def load_sources(root: Path, source_files: dict[str, str]) -> dict[str, dict]:
    return {label: json.loads((root / filename).read_text()) for label, filename in source_files.items()}
