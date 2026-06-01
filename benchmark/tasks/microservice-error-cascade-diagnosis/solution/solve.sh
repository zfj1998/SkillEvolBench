#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 <<'PYEOF'
from pathlib import Path

p = Path('config.py')
src = p.read_text(encoding='utf-8')
if 'quote_plus' not in src:
    src = src.replace('import os', 'import os\nfrom urllib.parse import quote_plus')
src = src.replace(
    "def get_connection_string() -> str:\n    \"\"\"Buggy: password is inserted raw and breaks URI parsing for special chars.\"\"\"\n    return f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'",
    "def get_connection_string() -> str:\n    \"\"\"Build a legal PostgreSQL URI even when password has special chars.\"\"\"\n    encoded_pw = quote_plus(DB_PASSWORD)\n    return f'postgresql://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME}'",
)
p.write_text(src, encoding='utf-8')

Path('db_client.py').write_text(
    '''"""Database client for ProfileHub."""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, unquote_plus

from config import DB_HOST, DB_NAME, DB_PORT, DB_USER, DB_PASSWORD, get_connection_string

_SEED_PROFILES: Dict[int, Dict[str, Any]] = {
    1: {'id': 1, 'username': 'alice', 'email': 'alice@example.com', 'display_name': 'Alice Zhang', 'bio': 'Engineering lead', 'avatar': '/img/alice.png'},
    2: {'id': 2, 'username': 'bob', 'email': 'bob@example.com', 'display_name': 'Bob Martinez', 'bio': 'Product designer', 'avatar': '/img/bob.png'},
    3: {'id': 3, 'username': 'carol', 'email': 'carol@example.com', 'display_name': 'Carol Okafor', 'bio': 'Data scientist', 'avatar': '/img/carol.png'},
}

_conn_params: Optional[Dict[str, Any]] = None
_connected: bool = False


class OperationalError(Exception):
    pass


def _parse_dsn(dsn: str) -> Dict[str, Any]:
    parsed = urlparse(dsn)
    return {
        'scheme': parsed.scheme,
        'user': parsed.username,
        'password': unquote_plus(parsed.password or ''),
        'host': parsed.hostname,
        'port': parsed.port,
        'database': (parsed.path or '').lstrip('/'),
    }


def _connect() -> None:
    global _conn_params, _connected
    params = _parse_dsn(get_connection_string())
    if params['host'] != DB_HOST or params['port'] != DB_PORT or params['database'] != DB_NAME:
        raise OperationalError('Connection to database timed out after 5000ms')
    if params['user'] != DB_USER or params['password'] != DB_PASSWORD:
        raise OperationalError('Connection to database timed out after 5000ms')
    _conn_params = params
    _connected = True


def _ensure_connected() -> None:
    if not _connected:
        _connect()


def reset_connection() -> None:
    global _conn_params, _connected
    _conn_params = None
    _connected = False


def fetch_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    _ensure_connected()
    return _SEED_PROFILES.get(user_id)


def fetch_all_profiles() -> List[Dict[str, Any]]:
    _ensure_connected()
    return list(_SEED_PROFILES.values())


def user_exists(user_id: int) -> bool:
    _ensure_connected()
    return user_id in _SEED_PROFILES
''',
    encoding='utf-8',
)

Path('user_service.py').write_text(
    '''"""User service for ProfileHub."""

from typing import Any, Dict, List, Optional

import db_client


def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    profile = db_client.fetch_user_profile(user_id)
    if profile is None:
        return None
    return dict(profile)


def list_users() -> List[Dict[str, Any]]:
    return db_client.fetch_all_profiles()


def check_user_exists(user_id: int) -> bool:
    return db_client.user_exists(user_id)
''',
    encoding='utf-8',
)

Path('api_gateway.py').write_text(
    '''"""API gateway for ProfileHub."""

from typing import Any, Dict, Tuple

import auth_service
import db_client
import user_service
from middleware import log_request


def handle_request(method: str, path: str, headers: Dict[str, str] = None, body: Dict[str, Any] = None) -> Tuple[int, Dict[str, Any]]:
    headers = headers or {}
    body = body or {}
    log_request(method, path)

    if path == '/api/login' and method == 'POST':
        return _handle_login(body)

    user_id = _authenticate_request(headers)
    if user_id is None:
        return 401, {'error': 'Authentication required'}

    if path == '/api/profile' and method == 'GET':
        return _handle_get_profile(user_id)

    if path.startswith('/api/profile/') and method == 'GET':
        target_user_id = int(path.rsplit('/', 1)[-1])
        return _handle_get_profile(target_user_id)

    if path == '/api/users' and method == 'GET':
        return _handle_list_users()

    return 404, {'error': 'Endpoint not found'}


def _handle_login(body: dict) -> Tuple[int, dict]:
    username = body.get('username', '')
    password = body.get('password', '')
    if not username or not password:
        return 400, {'error': 'Username and password required'}
    token = auth_service.authenticate(username, password)
    if token is None:
        return 401, {'error': 'Invalid credentials'}
    return 200, {'token': token, 'message': 'Login successful'}


def _handle_get_profile(user_id: int) -> Tuple[int, dict]:
    try:
        profile = user_service.get_user_profile(user_id)
    except db_client.OperationalError:
        return 503, {'error': 'service temporarily unavailable'}
    if profile is None:
        return 404, {'error': 'user not found'}
    return 200, {'profile': profile, 'has_profile': True}


def _handle_list_users() -> Tuple[int, dict]:
    try:
        users = user_service.list_users()
    except db_client.OperationalError:
        return 503, {'error': 'service temporarily unavailable'}
    return 200, {'users': users}


def _authenticate_request(headers: dict) -> int | None:
    auth_header = headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    return auth_service.validate_token(auth_header[7:])
''',
    encoding='utf-8',
)
PYEOF
