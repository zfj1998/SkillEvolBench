#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "encoding_contract.py": dedent(
        """
        from __future__ import annotations

        EXPECTED_HEADERS = ("region", "name", "amount", "quarter")


        def normalize_header(raw: str) -> str:
            return str(raw).replace("\\ufeff", "").strip().lower()


        def resolve_headers(headers) -> dict[str, str]:
            mapping = {normalize_header(header): header for header in headers}
            resolved: dict[str, str] = {}
            missing: list[str] = []
            for canonical in EXPECTED_HEADERS:
                actual = mapping.get(canonical)
                if actual is None:
                    missing.append(canonical)
                    continue
                resolved[canonical] = actual
            if missing:
                raise KeyError(f"missing expected headers: {missing}")
            return resolved
        """
    ),
    "revenue_cleaner.py": dedent(
        """
        from __future__ import annotations


        def parse_amount(raw: str) -> float:
            text = str(raw).replace("\\u200b", "").strip().replace(",", "")
            return float(text)
        """
    ),
    "process_revenue.py": dedent(
        """
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

            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
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
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
