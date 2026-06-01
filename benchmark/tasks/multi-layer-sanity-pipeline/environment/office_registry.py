from __future__ import annotations

import csv
from pathlib import Path


def inspect_offices(csv_path: Path) -> dict[str, object]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        "row_count": len(rows),
        "invalid_status_rows": [],
        "rows": rows,
    }
