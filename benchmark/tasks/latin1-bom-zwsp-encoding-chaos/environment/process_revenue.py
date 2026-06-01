from __future__ import annotations

import csv
import json
from pathlib import Path

from encoding_contract import resolve_headers
from revenue_cleaner import parse_amount

CSV_PATH = Path("revenue.csv")
OUTPUT_PATH = Path("output.json")


def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    region_totals: dict[str, float] = {}
    sample_names: set[str] = set()
    raw_headers: list[str] = []
    rejected_rows = 0
    loaded_rows = 0

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        raw_headers = list(reader.fieldnames or [])
        header_map = resolve_headers(raw_headers)

        for raw_row in reader:
            loaded_rows += 1
            row = {canonical: raw_row[actual] for canonical, actual in header_map.items()}
            try:
                amount = parse_amount(row["amount"])
            except ValueError:
                rejected_rows += 1
                continue
            region_totals[row["region"]] = region_totals.get(row["region"], 0.0) + amount
            sample_names.add(row["name"])

    payload = {
        "region_totals": {key: round(value, 2) for key, value in sorted(region_totals.items())},
        "row_count": loaded_rows,
        "clean_row_count": loaded_rows - rejected_rows,
        "sample_names": sorted(sample_names)[:12],
        "schema_report": {
            "raw_headers": raw_headers,
            "canonical_headers": list(resolve_headers(raw_headers).keys()),
            "rejected_rows": rejected_rows,
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
