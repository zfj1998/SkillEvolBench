#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path

project = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
source = project / "auth_client.py"
text = source.read_text(encoding="utf-8")
text = text.replace(
    "        action = classify_response(response)\n"
    "        if action == \"ok\":\n"
    "            return response[\"body\"]\n"
    "        if action == \"refresh\":\n"
    "            token = refresh_token(api, clock)\n"
    "            continue\n"
    "        if action == \"retry\" and retries < max_retries:\n"
    "            retries += 1\n"
    "            continue\n"
    "        raise RuntimeError(f\"request failed: {response['status']}\")\n",
    "        status = response[\"status\"]\n"
    "        if status == 200:\n"
    "            return response[\"body\"]\n"
    "        if status == 401 and response[\"body\"].get(\"error\") == \"token_expired\":\n"
    "            token = refresh_token(api, clock)\n"
    "            continue\n"
    "        if status == 503 and retries < max_retries:\n"
    "            retries += 1\n"
    "            continue\n"
    "        raise RuntimeError(f\"request failed: {status}\")\n",
)
text = text.replace("from auth_policy import classify_response\n", "")
source.write_text(text, encoding="utf-8")

policy = project / "auth_policy.py"
text = policy.read_text(encoding="utf-8")
text = text.replace('        return "retry"', '        return "refresh"', 1)
policy.write_text(text, encoding="utf-8")
print("Applied targeted auth-refresh retry fix.")
__SKILL_EVOL_SOLVE_PY_0__
