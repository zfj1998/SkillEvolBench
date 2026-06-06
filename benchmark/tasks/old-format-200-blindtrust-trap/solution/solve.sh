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
    "fetch_users.py": dedent(
        """
        from __future__ import annotations

        import json
        import logging
        from pathlib import Path

        import requests

        from compat_projection import project_user
        from field_aliases import load_contract

        API_URL = "http://localhost:5050/api/users"
        TOTAL_BATCHES = 2
        OUTPUT_PATH = Path("output.json")

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler("fetch_users.log"), logging.StreamHandler()],
        )
        logger = logging.getLogger(__name__)


        def run(output_path: Path = OUTPUT_PATH) -> list[dict]:
            contract = load_contract(Path("api_docs.md"))
            session = requests.Session()
            users: list[dict] = []
            for _ in range(TOTAL_BATCHES):
                response = session.get(API_URL, timeout=10)
                payload = response.json()
                for item in payload.get("data", []):
                    users.append(project_user(item, contract))
            output_path.write_text(json.dumps(users, indent=2), encoding="utf-8")
            return users


        if __name__ == "__main__":
            run()
        """
    ),
    "compat_projection.py": dedent(
        """
        from __future__ import annotations


        def project_user(raw: dict, contract: dict) -> dict:
            deprecated = contract["deprecated"]
            projected = {"id": raw["id"]}
            for canonical in ("username", "phone", "email", "created_at"):
                deprecated_name = deprecated[canonical]
                projected[canonical] = raw.get(canonical, raw.get(deprecated_name))
            return projected
        """
    )
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
