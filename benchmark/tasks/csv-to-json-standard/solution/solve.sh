#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
python3 - "$PROJECT_ROOT/type_inference.py" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("return float(value)", 'return float(value.replace(",", ""))')
path.write_text(text, encoding="utf-8")
PY
