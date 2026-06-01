"""Business logic for EventHub."""

from typing import Any, Dict, List, Optional

from app.database import get_user, get_all_users, require_database_url
from app.models import UserResponseSchema


def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    row = get_user(user_id)
    if row is None:
        return None
    return UserResponseSchema.from_record(row).to_api_dict()


def list_user_profiles() -> List[Dict[str, Any]]:
    return [UserResponseSchema.from_record(r).to_api_dict() for r in get_all_users()]


def get_active_users() -> List[Dict[str, Any]]:
    # CI bug: this helper assumes DATABASE_URL is configured, which is only true
    # in integration environments. The tests should patch this dependency.
    require_database_url()
    return [
        UserResponseSchema.from_record(u).to_api_dict()
        for u in get_all_users()
        if u.get('is_active') is True
    ]


def get_user_count_by_role() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for u in get_all_users():
        counts[u.get('role', 'unknown')] = counts.get(u.get('role', 'unknown'), 0) + 1
    return counts
