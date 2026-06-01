from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

TRACE: list[dict[str, Any]] = []
TASKS: dict[str, dict[str, Any]] = {}
MIN_POLL_INTERVAL = 1.0
REPORT_DATA = {'month': '2024-06', 'totals': {'new_signups': 42, 'revenue': 12500}, 'segments': ['self-serve', 'enterprise']}


class ApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def reset_state() -> None:
    TRACE.clear()
    TASKS.clear()


def _record(endpoint: str, status: int, payload: dict[str, Any] | None = None) -> None:
    TRACE.append({'endpoint': endpoint, 'status': status, 'payload': payload or {}, 'ts': time.monotonic()})


def create_report(month: str) -> dict[str, Any]:
    task_id = 'task-report-001'
    TASKS[task_id] = {'polls': 0, 'last_poll_ts': None}
    payload = {'task_id': task_id, 'status': 'pending', 'month': month}
    _record('/reports', 202, payload)
    return payload


def get_status(task_id: str) -> dict[str, Any]:
    task = TASKS[task_id]
    now = time.monotonic()
    if task['last_poll_ts'] is not None and now - task['last_poll_ts'] < MIN_POLL_INTERVAL:
        _record(f'/reports/{task_id}/status', 429, {'task_id': task_id, 'status': 'too_fast'})
        raise ApiError(429, 'too_fast', 'poll interval too short')
    task['last_poll_ts'] = now
    task['polls'] += 1
    status = 'completed' if task['polls'] >= 4 else 'processing'
    payload = {'task_id': task_id, 'status': status, 'poll_count': task['polls']}
    _record(f'/reports/{task_id}/status', 200, payload)
    return payload


def get_result(task_id: str) -> dict[str, Any]:
    task = TASKS[task_id]
    if task['polls'] < 4:
        _record(f'/reports/{task_id}/result', 404, {'task_id': task_id, 'status': 'not_ready'})
        raise ApiError(404, 'not_ready', 'result not ready')
    payload = {'task_id': task_id, 'report': REPORT_DATA}
    _record(f'/reports/{task_id}/result', 200, payload)
    return payload


def save_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding='utf-8')
