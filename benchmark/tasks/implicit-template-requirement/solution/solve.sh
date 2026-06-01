#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))
catalog = root / "placeholder_catalog.py"
text = catalog.read_text(encoding="utf-8")
text = text.replace(
    'PLACEHOLDER_PATTERNS = [r"\\[TBD\\]"]',
    'PLACEHOLDER_PATTERNS = [r"\\[TBD\\]", r"\\[INSERT HERE\\]", r"___", r"<PENDING>"]',
)
catalog.write_text(text, encoding="utf-8")
PY

python3 "$PROJECT_ROOT/complete_report.py"
