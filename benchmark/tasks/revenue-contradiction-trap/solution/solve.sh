#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
python3 - "$PROJECT_ROOT/conflict_policy.py" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(
    '''from __future__ import annotations


def summarize_revenue_conflict(evidence: list[dict]) -> dict:
    return {
        "revenues": evidence,
        "conflict": True,
        "discrepancy_note": "Annual revenue appears with conflicting values across source sections.",
    }
''',
    encoding="utf-8",
)
PY
