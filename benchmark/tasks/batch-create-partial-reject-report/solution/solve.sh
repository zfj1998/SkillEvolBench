#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path

project = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
source = project / "batch_import.py"
text = source.read_text(encoding="utf-8")
text = text.replace("from duplicate_guard import freeze_username_snapshot", "from duplicate_guard import existing_usernames")
text = text.replace("    username_snapshot = freeze_username_snapshot(CREATED)\n", "")
text = text.replace("        errors = screen_candidate(candidate, username_snapshot)", "        errors = screen_candidate(candidate, existing_usernames(CREATED))")
text = text.replace(
    '            failures.append({"row": candidate, "errors": errors})\n            return {"success": successes, "failures": failures, "summary": build_summary(rows, successes, failures)}',
    '            failures.append({"index": index, "errors": errors})\n            continue',
)
source.write_text(text, encoding="utf-8")
print("Applied targeted partial-batch validation fix.")
__SKILL_EVOL_SOLVE_PY_0__
