"""In-memory data store for EventHub."""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

_USERS: List[Dict[str, Any]] = [
    {'id': 1, 'username': 'alice', 'email': 'alice@corp.io', 'is_active': True, 'role': 'admin', 'created_at': '2024-01-15T10:00:00'},
    {'id': 2, 'username': 'bob', 'email': 'bob@corp.io', 'is_active': True, 'role': 'editor', 'created_at': '2024-03-22T14:30:00'},
    {'id': 3, 'username': 'carol', 'email': 'carol@corp.io', 'is_active': False, 'role': 'viewer', 'created_at': '2024-06-01T09:00:00'},
    {'id': 4, 'username': 'dave', 'email': 'dave@corp.io', 'is_active': True, 'role': 'viewer', 'created_at': '2024-07-10T11:15:00'},
    {'id': 5, 'username': 'eve', 'email': 'eve@corp.io', 'is_active': False, 'role': 'editor', 'created_at': '2024-09-05T16:45:00'},
]

_EVENTS: List[Dict[str, Any]] = []


def require_database_url() -> str:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise RuntimeError('DATABASE_URL is not configured for the test environment')
    return db_url


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    return next((dict(u) for u in _USERS if u['id'] == user_id), None)


def get_all_users() -> List[Dict[str, Any]]:
    return [dict(u) for u in _USERS]


def store_event(event: Dict[str, Any]) -> None:
    _EVENTS.append({**event, 'stored_at': datetime.now().isoformat()})


def get_events(event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    if event_type is None:
        return list(_EVENTS)
    return [e for e in _EVENTS if e.get('event_type') == event_type]


def clear_events() -> None:
    _EVENTS.clear()
