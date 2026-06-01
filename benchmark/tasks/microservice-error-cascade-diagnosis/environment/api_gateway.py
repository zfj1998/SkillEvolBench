"""API gateway for ProfileHub."""

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
    profile = user_service.get_user_profile(user_id)
    if profile is None:
        return 404, {'error': 'user not found'}
    if not profile:
        return 200, {'profile': {}, 'has_profile': False}
    return 200, {'profile': profile, 'has_profile': True}


def _handle_list_users() -> Tuple[int, dict]:
    users = user_service.list_users()
    return 200, {'users': users}


def _authenticate_request(headers: dict) -> int | None:
    auth_header = headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    return auth_service.validate_token(auth_header[7:])
