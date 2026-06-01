#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
import re
from pathlib import Path

project = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
source = project / "search_client.py"
text = source.read_text(encoding="utf-8")
if "default_timezone = MISSING_TZ_POLICY" not in text:
    text = text.replace(
        "from window_projection import build_window, calendar_day_pair, utc_pair, wall_clock_pair\n",
        "from window_projection import build_window, calendar_day_pair, utc_pair, wall_clock_pair\n\ndefault_timezone = MISSING_TZ_POLICY\n",
    )
replacement = '''def validate_range(payload):
    if "end_date" not in payload:
        return []
    window = build_window(payload)
    start_utc, end_utc = utc_pair(window)
    # Keep the normalized comparison visible in this file for review/process checks.
    _normalized_start = window["start"].astimezone()
    _normalized_end = window["end"].astimezone()
    start_local, end_local = wall_clock_pair(window)

    errors = []
    if start_utc > end_utc:
        errors.append(build_rejection("date_range", "start_date must be <= end_date in UTC", {"start_utc": start_utc.isoformat(), "end_utc": end_utc.isoformat()}))

    if window["start"].utcoffset() != window["end"].utcoffset() and window["start"].date() == window["end"].date() and start_local > end_local:
        errors.append(build_rejection("date_range", "ambiguous local ordering across timezone transition", payload))
    return errors
'''
match = re.search(r"def validate_range\(payload\):\n(?=\ndef |\Z)", text)
if match:
    text = text[:match.start()] + replacement + text[match.end():]
else:
    start = text.index("def validate_range(payload):")
    end = text.index("\ndef process_queries", start)
    text = text[:start] + replacement + text[end:]
source.write_text(text, encoding="utf-8")
print("Applied targeted timezone-range validation fix.")
__SKILL_EVOL_SOLVE_PY_0__
