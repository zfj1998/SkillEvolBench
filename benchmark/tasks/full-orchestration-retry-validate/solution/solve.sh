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
    "full_workflow.py": dedent("""
        from __future__ import annotations

        import json
        from pathlib import Path

        import mock_api
        from auth_session import authenticate_session, load_request
        from job_poller import poll_until_completed
        from result_validator import validate_result
        from spec_router import fetch_spec_for_user

        REQUEST_FILE = Path(__file__).with_name('request.json')


        def run(output_path: str | Path = 'validated_result.json'):
            request_payload = load_request(REQUEST_FILE)
            session = authenticate_session(mock_api, 'analyst', 'benchmark-pass')
            profile = mock_api.get_user_type(request_payload['user_id'], session['headers'])
            spec = fetch_spec_for_user(mock_api, profile, session['headers'])
            task = mock_api.submit_job(spec, session['headers'])
            poll_until_completed(mock_api, task['task_id'], session['headers'])
            result = mock_api.get_job_result(task['task_id'], session['headers'])['result']
            validated = validate_result(result, spec['expected_checksum'])
            Path(output_path).write_text(json.dumps(validated, indent=2), encoding='utf-8')
            return validated


        if __name__ == '__main__':
            run()
    """),
    "spec_router.py": dedent("""
        from __future__ import annotations


        def fetch_spec_for_user(api, profile: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
            if profile['tier'] == 'premium':
                return api.get_premium_spec(profile['user_id'], headers)
            return api.get_standard_spec(profile['user_id'], headers)
    """),
    "result_validator.py": dedent("""
        from __future__ import annotations


        def validate_result(result: dict[str, object], expected_checksum: str) -> dict[str, object]:
            required = {'approved', 'user_id', 'tier', 'records', 'checksum'}
            if not required <= set(result):
                raise ValueError('missing required result fields')
            if result['approved'] is not True:
                raise ValueError('result not approved')
            if result['checksum'] != expected_checksum:
                raise ValueError('checksum mismatch')
            return result
    """),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"Wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
