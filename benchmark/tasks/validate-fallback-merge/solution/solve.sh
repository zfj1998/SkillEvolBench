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
    "record_validator.py": dedent(
        """
        from __future__ import annotations

        REQUIRED_KEYS = {"id", "name", "price", "currency", "in_stock", "updated_at"}


        def is_valid_record(record: dict) -> bool:
            if not isinstance(record, dict):
                return False
            if not REQUIRED_KEYS.issubset(record):
                return False
            name = record.get("name")
            price = record.get("price")
            if not isinstance(name, str) or not name.strip():
                return False
            return isinstance(price, (int, float)) and price >= 0
        """
    )
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
