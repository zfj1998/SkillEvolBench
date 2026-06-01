from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

TRACE: list[dict[str, Any]] = []
TOKEN = 'token-e2-ls4-t6'
MIN_POLL_INTERVAL = 0.5
USERS = {
    'user_1': {'tier': 'premium', 'execution_path_hint': 'standard'},
    'user_2': {'tier': 'standard', 'execution_path_hint': 'standard'},
}
TASKS: dict[str, dict[str, Any]] = {}


class ApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def reset_state() -> None:
    TRACE.clear()
    TASKS.clear()


def _record(endpoint: str, status: int, headers: dict[str, str] | None = None, response: dict[str, Any] | None = None, extra: dict[str, Any] | None = None) -> None:
    TRACE.append({'endpoint': endpoint, 'status': status, 'headers': dict(headers or {}), 'response': response or {}, 'extra': extra or {}, 'ts': time.monotonic()})


def _require_token(headers: dict[str, str] | None, endpoint: str) -> None:
    auth = (headers or {}).get('Authorization', '')
    if auth != f'Bearer {TOKEN}':
        _record(endpoint, 401, headers=headers, response={'error': 'unauthorized'})
        raise ApiError(401, 'unauthorized', 'missing token')


def authenticate(username: str, password: str) -> dict[str, str]:
    if username == 'analyst' and password == 'benchmark-pass':
        payload = {'access_token': TOKEN}
        _record('/auth', 200, response=payload)
        return payload
    _record('/auth', 401, response={'error': 'bad_credentials'})
    raise ApiError(401, 'bad_credentials', 'invalid credentials')


def get_user_type(user_id: str, headers: dict[str, str]) -> dict[str, Any]:
    endpoint = f'/users/{user_id}'
    _require_token(headers, endpoint)
    payload = {'user_id': user_id, 'tier': USERS[user_id]['tier'], 'execution_path_hint': USERS[user_id]['execution_path_hint']}
    _record(endpoint, 200, headers=headers, response=payload)
    return payload


def get_premium_spec(user_id: str, headers: dict[str, str]) -> dict[str, Any]:
    endpoint = '/premium/spec'
    _require_token(headers, endpoint)
    payload = {'user_id': user_id, 'job_kind': 'priority-review', 'expected_checksum': 'chk-premium'}
    _record(endpoint, 200, headers=headers, response=payload)
    return payload


def get_standard_spec(user_id: str, headers: dict[str, str]) -> dict[str, Any]:
    endpoint = '/standard/spec'
    _require_token(headers, endpoint)
    payload = {'user_id': user_id, 'job_kind': 'standard-review', 'expected_checksum': 'chk-standard'}
    _record(endpoint, 200, headers=headers, response=payload)
    return payload


def submit_job(spec: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    endpoint = '/jobs'
    _require_token(headers, endpoint)
    task_id = 'job-001'
    TASKS[task_id] = {'status_calls': 0, 'last_poll_ts': None, 'spec': spec}
    payload = {'task_id': task_id, 'status': 'pending', 'job_kind': spec['job_kind']}
    _record(endpoint, 202, headers=headers, response=payload, extra={'job_kind': spec['job_kind']})
    return payload


def get_job_status(task_id: str, headers: dict[str, str]) -> dict[str, Any]:
    endpoint = f'/jobs/{task_id}/status'
    _require_token(headers, endpoint)
    task = TASKS[task_id]
    now = time.monotonic()
    if task['last_poll_ts'] is not None and now - task['last_poll_ts'] < MIN_POLL_INTERVAL:
        _record(endpoint, 429, headers=headers, response={'error': 'too_fast'})
        raise ApiError(429, 'too_fast', 'polling too quickly')
    task['last_poll_ts'] = now
    task['status_calls'] += 1
    if task['status_calls'] == 2:
        _record(endpoint, 503, headers=headers, response={'error': 'temporary_unavailable'})
        raise ApiError(503, 'temporary_unavailable', 'try again')
    status = 'completed' if task['status_calls'] >= 4 else 'processing'
    payload = {'task_id': task_id, 'status': status, 'status_calls': task['status_calls']}
    _record(endpoint, 200, headers=headers, response=payload)
    return payload


def get_job_result(task_id: str, headers: dict[str, str]) -> dict[str, Any]:
    endpoint = f'/jobs/{task_id}/result'
    _require_token(headers, endpoint)
    task = TASKS[task_id]
    if task['status_calls'] < 4:
        _record(endpoint, 404, headers=headers, response={'error': 'not_ready'})
        raise ApiError(404, 'not_ready', 'result not ready')
    tier = 'premium' if task['spec']['job_kind'] == 'priority-review' else 'standard'
    payload = {
        'task_id': task_id,
        'result': {
            'approved': True,
            'user_id': task['spec']['user_id'],
            'tier': tier,
            'records': [{'step': 'analysis', 'score': 98}],
            'checksum': task['spec']['expected_checksum'],
        },
    }
    _record(endpoint, 200, headers=headers, response=payload)
    return payload


def save_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding='utf-8')
