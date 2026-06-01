from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

TRACE: list[dict[str, Any]] = []
_DETAIL_CALLS: list[float] = []
TOKEN = 'token-e2-ls4-t1'
ITEMS = [
    {'id': 'item-1', 'name': 'alpha', 'category': 'core', 'score': 11},
    {'id': 'item-2', 'name': 'beta', 'category': 'core', 'score': 13},
    {'id': 'item-3', 'name': 'gamma', 'category': 'growth', 'score': 17},
    {'id': 'item-4', 'name': 'delta', 'category': 'growth', 'score': 19},
    {'id': 'item-5', 'name': 'epsilon', 'category': 'edge', 'score': 23},
]


class ApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def reset_state() -> None:
    TRACE.clear()
    _DETAIL_CALLS.clear()


def _record(endpoint: str, status: int, headers: dict[str, str] | None = None, response: dict[str, Any] | None = None, extra: dict[str, Any] | None = None) -> None:
    TRACE.append({'endpoint': endpoint, 'status': status, 'headers': dict(headers or {}), 'response': response or {}, 'extra': extra or {}, 'ts': time.monotonic()})


def _require_token(headers: dict[str, str] | None, endpoint: str) -> None:
    auth = (headers or {}).get('Authorization', '')
    if auth != f'Bearer {TOKEN}':
        _record(endpoint, 401, headers=headers, response={'error': 'unauthorized'})
        raise ApiError(401, 'unauthorized', 'missing or invalid bearer token')


def authenticate(username: str, password: str) -> dict[str, str]:
    if username == 'analyst' and password == 'benchmark-pass':
        payload = {'access_token': TOKEN, 'token_type': 'Bearer'}
        _record('/auth', 200, response=payload)
        return payload
    _record('/auth', 401, response={'error': 'bad_credentials'})
    raise ApiError(401, 'bad_credentials', 'invalid credentials')


def list_items(headers: dict[str, str]) -> dict[str, Any]:
    _require_token(headers, '/items')
    payload = {'items': [{'id': item['id']} for item in ITEMS]}
    _record('/items', 200, headers=headers, response=payload)
    return payload


def get_item_detail(item_id: str, headers: dict[str, str]) -> dict[str, Any]:
    endpoint = f'/items/{item_id}'
    _require_token(headers, endpoint)
    now = time.monotonic()
    recent = [stamp for stamp in _DETAIL_CALLS if now - stamp < 1.0]
    _DETAIL_CALLS[:] = recent
    if len(recent) >= 3:
        _record(endpoint, 429, headers=headers, response={'error': 'too_many_requests'})
        raise ApiError(429, 'too_many_requests', 'detail endpoint rate limited')
    _DETAIL_CALLS.append(now)
    for item in ITEMS:
        if item['id'] == item_id:
            payload = {'id': item['id'], 'name': item['name'], 'category': item['category'], 'score': item['score'], 'source': 'detail'}
            _record(endpoint, 200, headers=headers, response=payload, extra={'item_id': item_id})
            return payload
    _record(endpoint, 404, headers=headers, response={'error': 'not_found'})
    raise ApiError(404, 'not_found', f'{item_id} not found')


def save_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding='utf-8')
