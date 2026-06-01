"""API routes for user profiles."""
import json
from backend.http_policy import success_status
from backend.services import get_user_profile


def handle_get_user(user_id):
    """Handle GET /api/user/<id>.

    Always returns HTTP 200, even when there's an error.
    """
    result = get_user_profile(user_id)
    return json.dumps(result), success_status()  # Always 200!
