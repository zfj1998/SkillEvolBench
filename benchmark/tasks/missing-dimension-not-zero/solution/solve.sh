#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

cat > "$PROJECT_ROOT/missingness_policy.py" <<'PYMOD'
from __future__ import annotations


def normalize(value):
    return value if value is not None else "unavailable"
PYMOD

cat > "$PROJECT_ROOT/matrix_pipeline.py" <<'PYMOD'
from __future__ import annotations

import json
from pathlib import Path

from missingness_policy import normalize
from provenance import provenance_block

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)


def main():
    rows = [
        {"dimension": "security", "salesforce": "documented", "hubspot": normalize(None)},
        {"dimension": "marketplace_scale", "salesforce": "documented", "hubspot": "documented"},
        {"dimension": "fedramp", "salesforce": "documented", "hubspot": normalize(None)},
    ]
    payload = {
        "rows": rows,
        "provenance": provenance_block(
            ["C03", "C04", "C05", "C06", "C08", "C09"],
            "Missing vendor dimensions are represented as unavailable, not zero or false.",
            ["Unavailable means no supporting source was found in the provided manifest."],
        ),
    }
    (OUTPUT / "comparison_matrix.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
PYMOD
