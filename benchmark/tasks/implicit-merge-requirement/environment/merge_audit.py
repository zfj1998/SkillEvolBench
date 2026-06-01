from __future__ import annotations

import json
from pathlib import Path


def write_audit(path: Path, raw_count: int, unique_count: int, sources: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "raw_records": raw_count,
                "unique_records": unique_count,
                "sources_seen": sources,
                "dedup_method": "normalized email",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
