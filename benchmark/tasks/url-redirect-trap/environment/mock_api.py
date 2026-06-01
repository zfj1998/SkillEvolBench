from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRACE: list[dict[str, Any]] = []
CONFIG = {
    'data_endpoint': '/v2/data?token=current',
    'deprecated_endpoint': '/v1/data?token=legacy',
    'migration_state': 'dual-read',
}
V1_DATA = {'version': 'v1', 'records': [{'date': '2023-11-01', 'value': 71}, {'date': '2023-12-01', 'value': 74}]}
V2_DATA = {'version': 'v2', 'records': [{'date': '2024-11-01', 'value': 81}, {'date': '2024-12-01', 'value': 84}]}


def reset_state() -> None:
    TRACE.clear()


def get_config() -> dict[str, str]:
    TRACE.append({'endpoint': '/config'})
    return dict(CONFIG)


def fetch_data(endpoint: str) -> dict[str, Any]:
    TRACE.append({'endpoint': endpoint})
    if endpoint.startswith('/v1/data'):
        return V1_DATA
    if endpoint.startswith('/v2/data'):
        return V2_DATA
    raise ValueError(f'unknown endpoint: {endpoint}')


def save_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding='utf-8')
