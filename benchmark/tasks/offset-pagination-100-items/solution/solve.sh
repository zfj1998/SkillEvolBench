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
    offset = 0
    limit = 20
    users = []
    seen_ids = set()
    expected_total = None

    while True:
        response = api.fetch_users(offset=offset, limit=limit)
        expected_total = response["total"]
        for user in response["data"]:
            user_id = user["id"]
            if user_id in seen_ids:
                continue
            seen_ids.add(user_id)
            users.append(user)
        if not response["has_more"]:
            break
        offset += limit

    if expected_total is not None and len(users) != expected_total:
        raise ValueError(f"expected {expected_total} users, got {len(users)}")
    return users


def main():
    api = build_api()
    result = solve(api)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    TRACE.write_text(json.dumps(api.export_state(), indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_SOLUTION_PY_0__
cat <<'PY' > "$PROJECT_ROOT/offset_plan.py"
from __future__ import annotations

DEFAULT_LIMIT = 20


def build_request(offset: int, limit: int = DEFAULT_LIMIT) -> dict:
    return {"offset": offset, "limit": limit}


def next_offset(current_offset: int, response: dict, request_limit: int) -> int:
    return current_offset + request_limit


def should_continue(response: dict) -> bool:
    return bool(response.get("has_more"))
PY
cat <<'PY' > "$PROJECT_ROOT/user_buffer.py"
from __future__ import annotations


def merge_page(existing_rows: list[dict], page_rows: list[dict]) -> list[dict]:
    seen_ids = {row["id"] for row in existing_rows}
    for row in page_rows:
        row_id = row["id"]
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        existing_rows.append(row)
    return existing_rows
PY
echo "Oracle solution applied for E2-LS3-T1."
