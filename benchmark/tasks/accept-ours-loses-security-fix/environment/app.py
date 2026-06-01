"""Application routes."""
from database import get_user_by_id, get_all_users, create_user


def handle_get_user(user_id):
    user = get_user_by_id(user_id)
    if user:
        return {"status": "ok", "user": user}
    return {"status": "error", "message": "User not found"}


def handle_search(query):
    try:
        from database import search_users
        results = search_users(query)
        return {"status": "ok", "results": results, "count": len(results)}
    except (ImportError, AttributeError):
        return {"status": "error", "message": "Search not available"}


def handle_create_user(name, email):
    user_id = create_user(name, email)
    return {"status": "ok", "user_id": user_id}
