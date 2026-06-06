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

(project / 'client.py').write_text('import json\nfrom pathlib import Path\n\nfrom mock_api import TRACE, fetch_weather\nfrom request_audit import build_failure_entry, summarize_batch\nfrom validation_contract import WEATHER_RULES\n\n\ndef validate_request(request):\n    errors = []\n\n    city = request.get("city")\n    if city is None:\n        errors.append({"param": "city", "error": "required", "value": city, "expected": WEATHER_RULES["city"]})\n    elif not isinstance(city, str):\n        errors.append({"param": "city", "error": "type", "value": city, "expected": WEATHER_RULES["city"]})\n    elif not city.strip():\n        errors.append({"param": "city", "error": "required", "value": city, "expected": WEATHER_RULES["city"]})\n\n    days = request.get("days")\n    if not isinstance(days, int):\n        errors.append({"param": "days", "error": "type", "value": days, "expected": WEATHER_RULES["days"]})\n    elif days < 1 or days > 14:\n        errors.append({"param": "days", "error": "range", "value": days, "expected": WEATHER_RULES["days"]})\n\n    units = request.get("units")\n    if units not in {"metric", "imperial"}:\n        errors.append({"param": "units", "error": "enum", "value": units, "expected": WEATHER_RULES["units"]})\n\n    return errors\n\n\ndef process_requests(path):\n    TRACE.clear()\n    payload = json.loads(Path(path).read_text(encoding="utf-8"))\n    successes = []\n    failures = []\n    for index, request in enumerate(payload):\n        errors = validate_request(request)\n        if errors:\n            failures.append(build_failure_entry(index, request, errors))\n            continue\n        successes.append(fetch_weather(**request))\n    return summarize_batch(successes, failures, TRACE)\n', encoding="utf-8")

print("Oracle solution applied for E2-LS1-T1-multi-param-type-and-range-check.")
__SKILL_EVOL_SOLVE_PY_0__
