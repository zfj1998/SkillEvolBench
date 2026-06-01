"""Business logic layer for user profiles."""
from backend.database import db
from backend.error_payloads import not_found_payload, server_error_payload


def get_user_profile(user_id):
    """Get user profile data.

    BUG: Catches ALL exceptions silently and returns a normal-looking response.
    The caller (routes.py) always returns HTTP 200, hiding the error from the frontend.
    """
    try:
        user = db.get_user(user_id)
        if not user:
            return not_found_payload()
        return {"status": "ok", "data": user}
    except Exception:
        # Swallows ConnectionError (and everything else) silently
        return server_error_payload("Something went wrong")
