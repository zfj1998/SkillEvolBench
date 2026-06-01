"""User service for ProfileHub."""

from typing import Any, Dict, List, Optional

import db_client


def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    try:
        profile = db_client.fetch_user_profile(user_id)
    except Exception:
        return {}
    if profile is None:
        return None
    return dict(profile)


def list_users() -> List[Dict[str, Any]]:
    try:
        return db_client.fetch_all_profiles()
    except Exception:
        return []


def check_user_exists(user_id: int) -> bool:
    return db_client.user_exists(user_id)
