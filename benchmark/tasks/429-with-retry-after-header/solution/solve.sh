#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path

project = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
source = project / "retry_client.py"
text = source.read_text(encoding="utf-8")
text = text.replace(
    '                clock.sleep(compute_wait_seconds(response["headers"], case_id))',
    '                retry_after = int(response["headers"].get("Retry-After", "0"))\n                clock.sleep(retry_after)',
)
source.write_text(text, encoding="utf-8")
print("Applied targeted Retry-After handling fix.")
__SKILL_EVOL_SOLVE_PY_0__
