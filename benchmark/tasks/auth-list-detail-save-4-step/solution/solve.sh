#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "workflow.py": dedent("""
        from __future__ import annotations

        import json
        from pathlib import Path

        import mock_api
        from auth_session import authenticate_session, load_credentials
        from detail_collector import collect_details

        CREDENTIALS_FILE = Path(__file__).with_name("credentials.json")


        def run(output_path: str | Path = "output.json"):
            credentials = load_credentials(CREDENTIALS_FILE)
            session = authenticate_session(mock_api, credentials)
            items = mock_api.list_items(session["headers"])["items"]
            details = collect_details(mock_api, items, session)
            Path(output_path).write_text(json.dumps(details, indent=2), encoding="utf-8")
            return details


        if __name__ == "__main__":
            run()
    """),
    "request_budget.py": dedent("""
        from __future__ import annotations

        import time

        RATE_LIMIT_WINDOW_SECONDS = 1.05
        BATCH_SIZE = 3


        def wait_before_detail(index: int) -> None:
            if index > 1 and (index - 1) % BATCH_SIZE == 0:
                time.sleep(RATE_LIMIT_WINDOW_SECONDS)
    """),
    "detail_collector.py": dedent("""
        from __future__ import annotations

        from request_budget import wait_before_detail


        def collect_details(api, items: list[dict[str, str]], session: dict[str, object]) -> list[dict]:
            headers = session["headers"]
            details = []
            for index, item in enumerate(items, start=1):
                wait_before_detail(index)
                details.append(api.get_item_detail(item["id"], headers))
            return details
    """),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"Wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
