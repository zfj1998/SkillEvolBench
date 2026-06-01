"""Notification system - new feature from develop branch."""


def send_notification(user_id, message):
    """Send a notification to a user."""
    print(f"Notification to user {user_id}: {message}")
    return True


def get_notifications(user_id):
    """Get notifications for a user."""
    return [
        {"id": 1, "message": "Welcome!", "read": False},
    ]
