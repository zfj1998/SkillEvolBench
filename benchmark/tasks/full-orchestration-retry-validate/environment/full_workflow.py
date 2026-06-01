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
