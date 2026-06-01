#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))
path = root / "order_client.py"
text = path.read_text(encoding="utf-8")
if "import uuid" not in text:
    text = text.replace("from __future__ import annotations\n\n", "from __future__ import annotations\n\nimport uuid\n\n")
text = text.replace(
    '    attempts_log = []\n'
    '    for attempt in range(max_attempts):\n'
    '        headers, payload = build_create_request(body)\n',
    '    attempts_log = []\n'
    '    idempotency_key = str(uuid.uuid4())\n'
    '    headers = {"Idempotency-Key": idempotency_key}\n'
    '    payload = dict(body)\n'
    '    for attempt in range(max_attempts):\n',
)
path.write_text(text, encoding="utf-8")
PY
