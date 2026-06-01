"""Database client for ProfileHub."""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from config import get_connection_string

_SEED_PROFILES: Dict[int, Dict[str, Any]] = {
    1: {'id': 1, 'username': 'alice', 'email': 'alice@example.com', 'display_name': 'Alice Zhang', 'bio': 'Engineering lead', 'avatar': '/img/alice.png'},
    2: {'id': 2, 'username': 'bob', 'email': 'bob@example.com', 'display_name': 'Bob Martinez', 'bio': 'Product designer', 'avatar': '/img/bob.png'},
    3: {'id': 3, 'username': 'carol', 'email': 'carol@example.com', 'display_name': 'Carol Okafor', 'bio': 'Data scientist', 'avatar': '/img/carol.png'},
}

_connected: bool = False


class OperationalError(Exception):
    pass


def _connect() -> None:
    global _connected
    dsn = get_connection_string()
    parsed = urlparse(dsn)
    # Bug: raw special characters in password make urlparse treat part of the
    # password as the host section, so even local config looks like a timeout.
    if parsed.hostname != 'localhost' or parsed.port != 5432:
        raise OperationalError('Connection to database timed out after 5000ms')
    _connected = True


def _ensure_connected() -> None:
    if not _connected:
        _connect()


def reset_connection() -> None:
    global _connected
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
