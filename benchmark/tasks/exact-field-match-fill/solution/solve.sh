#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))
contract = root / "field_contract.py"
text = contract.read_text(encoding="utf-8")
text = text.replace('"start_date": ["Start Date"],', '"start_date": ["Start Date", "Start_Date"],')
contract.write_text(text, encoding="utf-8")
PY

python3 "$PROJECT_ROOT/fill_employee_form.py"
