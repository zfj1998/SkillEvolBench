"""Database tests."""
import os
import sys
import pytest
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from setup_db import setup_database


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    setup_database(db_path)
    import database
    database.DB_PATH = db_path
    yield
    if os.path.exists(db_path):
        os.remove(db_path)


class TestUserQueries:
    def test_get_user_by_id(self):
        from database import get_user_by_id
        user = get_user_by_id(1)
        assert user is not None
        assert user["name"] == "Alice Smith"

    def test_get_all_users(self):
        from database import get_all_users
        users = get_all_users()
        assert len(users) == 4

    def test_search_users(self):
        from database import search_users
        results = search_users("Alice")
        assert len(results) == 2

    def test_search_no_results(self):
        from database import search_users
        results = search_users("Nonexistent")
        assert len(results) == 0

    def test_create_user(self):
        from database import create_user, get_all_users
        create_user("Test User", "test@example.com")
        users = get_all_users()
        assert len(users) == 5
