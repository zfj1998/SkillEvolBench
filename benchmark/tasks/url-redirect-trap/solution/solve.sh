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
    "latest_data.py": dedent("""
        from __future__ import annotations

        import mock_api
        from endpoint_registry import resolve_data_endpoint
        from payload_writer import write_payload


        def run(output_path: str = 'latest_data.json'):
            config = mock_api.get_config()
            data = mock_api.fetch_data(resolve_data_endpoint(config))
            write_payload(output_path, data)
            return data


        if __name__ == '__main__':
            run()
    """),
    "endpoint_registry.py": dedent("""
        from __future__ import annotations


        def resolve_data_endpoint(config: dict[str, str]) -> str:
            return config['data_endpoint']
    """),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"Wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
