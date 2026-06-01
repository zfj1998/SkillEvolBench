#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

TASK_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()
PROJECT_ROOT = TASK_ROOT / "project" if (TASK_ROOT / "project").exists() else TASK_ROOT

FILES = {
    "report_workflow.py": dedent("""
        from __future__ import annotations

        import json
        from pathlib import Path

        import mock_api
        from polling_policy import wait_for_next_poll
        from report_client import create_report_task, fetch_report_result, fetch_report_status
        from status_gate import is_result_ready

        REQUEST_FILE = Path(__file__).with_name('request.json')


        def run(output_path: str | Path = 'report_output.json'):
            month = json.loads(REQUEST_FILE.read_text(encoding='utf-8'))['month']
            task = create_report_task(mock_api, month)
            while True:
                status = fetch_report_status(mock_api, task['task_id'])
                if is_result_ready(status):
                    break
                wait_for_next_poll()
            report = fetch_report_result(mock_api, task['task_id'])
            Path(output_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
            return report


        if __name__ == '__main__':
            run()
    """),
    "status_gate.py": dedent("""
        from __future__ import annotations


        def is_result_ready(status_payload: dict[str, object]) -> bool:
            return status_payload['status'] == 'completed'
    """),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"Wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
