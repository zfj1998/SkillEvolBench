from __future__ import annotations

import json
from pathlib import Path


def load_request(path: str | Path) -> dict[str, str]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def authenticate_session(api, username: str, password: str) -> dict[str, object]:
    auth = api.authenticate(username, password)
    token = auth['access_token']
    return {'token': token, 'headers': {'Authorization': f'Bearer {token}'}}
