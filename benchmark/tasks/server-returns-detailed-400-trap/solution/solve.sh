#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path

project = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
project.mkdir(parents=True, exist_ok=True)

(project / 'client.py').write_text('import json\nfrom pathlib import Path\n\nfrom error_presenter import build_local_error\nimport mock_api_v1 as backend\n\n\ndef validate_payload(payload):\n    errors = []\n    if not payload.get("city"):\n        errors.append({"field": "city", "message": "city required"})\n\n    days = payload.get("days")\n    if not isinstance(days, int):\n        errors.append({"field": "days", "message": "days must be an integer"})\n    elif days < 1 or days > 14:\n        errors.append({"field": "days", "message": "days out of range"})\n\n    units = payload.get("units")\n    if units not in {"metric", "imperial"}:\n        errors.append({"field": "units", "message": "units invalid"})\n    return errors\n\n\ndef process_requests(path):\n    payload = json.loads(Path(path).read_text(encoding="utf-8"))\n    successes = []\n    failures = []\n    backend.TRACE.clear()\n\n    for item in payload:\n        local_errors = validate_payload(item)\n        if local_errors:\n            failures.append(build_local_error(local_errors[0]))\n            continue\n\n        response = backend.call_api(item)\n        if response["status"] != 200:\n            failures.append(build_local_error({"field": "request", "message": "unexpected remote validation failure"}))\n            continue\n        successes.append(response["body"]["payload"])\n\n    return {"successes": successes, "failures": failures, "trace": list(backend.TRACE)}\n', encoding="utf-8")

print("Oracle solution applied for E2-LS1-T5-server-returns-detailed-400-trap.")
__SKILL_EVOL_SOLVE_PY_0__
