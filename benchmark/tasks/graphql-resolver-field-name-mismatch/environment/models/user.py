"""User database model."""

# Simulated database - stores data in snake_case (Python convention)
USERS_DB = [
    {"id": "1", "user_name": "alice", "email_address": "alice@example.com",
     "first_name": "Alice", "last_name": "Smith", "created_at": "2024-01-15"},
    {"id": "2", "user_name": "bob", "email_address": "bob@example.com",
     "first_name": "Bob", "last_name": "Jones", "created_at": "2024-02-20"},
    {"id": "3", "user_name": "charlie", "email_address": "charlie@example.com",
     "first_name": "Charlie", "last_name": "Brown", "created_at": "2024-03-10"},
    {"id": "4", "user_name": "diana", "email_address": "diana@example.com",
     "first_name": "Diana", "last_name": "Prince", "created_at": "2024-04-05"},
    {"id": "5", "user_name": "eve", "email_address": "eve@example.com",
     "first_name": "Eve", "last_name": "Wilson", "created_at": "2024-05-12"},
]


def get_user_by_id(user_id):
    """Find a user by ID."""
    for user in USERS_DB:
        if user["id"] == str(user_id):
            return dict(user)
    return None


def get_all_users():
    """Get all users."""
    return [dict(u) for u in USERS_DB]
