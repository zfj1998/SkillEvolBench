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
    "join_selector.py": dedent(
        """
        from __future__ import annotations


        def choose_join_columns(user_columns: list[str], transaction_columns: list[str]) -> tuple[str, str]:
            if "id" in user_columns and "user_id" in transaction_columns:
                return "id", "user_id"
            raise KeyError("Expected users.id and transactions.user_id")
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
