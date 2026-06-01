"""Basic GraphQL tests - demonstrate the issue."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import execute_query


def test_user_query_returns_data():
    """User query should return non-null data."""
    query = """
    query { user(id: "1") { id userName emailAddress } }
    """
    result = execute_query(query, {"id": "1"})
    assert result["data"]["user"] is not None


def test_user_fields_not_null():
    """User fields should not be null."""
    query = """
    query { user(id: "1") { id userName emailAddress } }
    """
    result = execute_query(query, {"id": "1"})
    user = result["data"]["user"]
    # These will fail if resolver returns wrong key names
    assert user.get("userName") is not None, "userName is null"
    assert user.get("emailAddress") is not None, "emailAddress is null"
