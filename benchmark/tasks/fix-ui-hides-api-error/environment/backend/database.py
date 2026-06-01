"""Database connection module - simulates occasional failures."""


class DatabaseConnection:
    def __init__(self):
        self._call_count = 0

    def get_user(self, user_id):
        """Get user from database. Raises ConnectionError occasionally."""
        self._call_count += 1

        # Simulate intermittent connection failures
        if self._call_count % 3 == 0:
            raise ConnectionError("Database connection lost")

        users = {
            1: {"id": 1, "name": "Alice Smith", "email": "alice@example.com", "role": "admin"},
            2: {"id": 2, "name": "Bob Jones", "email": "bob@example.com", "role": "user"},
            3: {"id": 3, "name": "Charlie Brown", "email": "charlie@example.com", "role": "user"},
        }
        return users.get(user_id)


db = DatabaseConnection()
