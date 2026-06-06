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
    "schema_router.py": dedent(
        """
        from __future__ import annotations


        def extract_products(payload: dict, prefer_top_level: bool) -> list[dict]:
            result = payload.get("result")
            if isinstance(result, dict) and isinstance(result.get("items"), list):
                return result["items"]

            if isinstance(payload.get("data"), list):
                return payload["data"]
            return []
        """
    ),
    "rollout_policy.py": dedent(
        """
        from __future__ import annotations


        def prefer_top_level_data(payload: dict) -> bool:
            return False
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
