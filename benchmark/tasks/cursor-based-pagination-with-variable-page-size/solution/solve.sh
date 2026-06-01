#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/solution.py" <<'__SKILL_EVOL_REFERENCE_SOLUTION_PY_0__'
from __future__ import annotations

import json
from pathlib import Path

from mock_api import build_api

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output.json"
TRACE = HERE / "trace.json"


def solve(api):
    cursor = None
    events = []
    seen_ids = set()

    while True:
        response = api.fetch_events(cursor=cursor)
        for event in response["data"]:
            event_id = event["id"]
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            events.append(event)
        if response["next_cursor"] is None:
            break
        cursor = response["next_cursor"]

    if len(events) != 80:
        raise ValueError(f"expected 80 events, got {len(events)}")
    return events


def main():
    api = build_api()
    result = solve(api)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    TRACE.write_text(json.dumps(api.export_state(), indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_SOLUTION_PY_0__
cat <<'PY' > "$PROJECT_ROOT/cursor_contract.py"
from __future__ import annotations


def build_request(cursor, limit=None):
    return {"cursor": cursor}


def next_cursor(response: dict):
    return response.get("next_cursor")
PY
cat <<'PY' > "$PROJECT_ROOT/cursor_checkpoint.py"
from __future__ import annotations


def normalize_cursor(token: str | None):
    return token
PY
echo "Oracle solution applied for E2-LS3-T2."
