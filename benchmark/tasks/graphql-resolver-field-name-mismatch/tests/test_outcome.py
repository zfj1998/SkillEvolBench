"""Outcome verifier for E1-LS4-T2: graphql-resolver-field-name-mismatch."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))


# ============================================================
# PUBLIC TESTS (2)
# ============================================================

class TestPublic:
    def test_user_query_returns_non_null(self):
        """User query should return non-null user data."""
        from app import execute_query
        query = 'query { user(id: "1") { id userName emailAddress } }'
        result = execute_query(query, {"id": "1"})
        assert result["data"]["user"] is not None

    def test_schema_fields_present(self):
        """Schema should define expected User fields."""
        schema_path = os.path.join(os.path.dirname(__file__), "..", "project", "schema.graphql")
        with open(schema_path) as f:
            schema = f.read()
        assert "userName" in schema
        assert "emailAddress" in schema


# ============================================================
# HIDDEN TESTS (5)
# ============================================================

class TestHidden:
    def test_h1_username_not_null(self):
        """H1: userName field should not be null."""
        from app import execute_query
        query = 'query { user(id: "1") { id userName } }'
        result = execute_query(query, {"id": "1"})
        user = result["data"]["user"]
        assert user["userName"] is not None, "userName is null - field name mismatch"

    def test_h2_email_address_not_null(self):
        """H2: emailAddress field should not be null."""
        from app import execute_query
        query = 'query { user(id: "1") { id emailAddress } }'
        result = execute_query(query, {"id": "1"})
        user = result["data"]["user"]
        assert user["emailAddress"] is not None, "emailAddress is null - field name mismatch"

    def test_h3_field_values_match_db(self):
        """H3: All field values should match database records."""
        from app import execute_query
        from models.user import get_user_by_id

        query = 'query { user(id: "1") { id userName emailAddress firstName lastName } }'
        result = execute_query(query, {"id": "1"})
        user = result["data"]["user"]
        db_user = get_user_by_id("1")

        assert user["userName"] == db_user["user_name"], (
            f"userName mismatch: API={user['userName']}, DB={db_user['user_name']}"
        )
        assert user["emailAddress"] == db_user["email_address"], (
            f"emailAddress mismatch: API={user['emailAddress']}, DB={db_user['email_address']}"
        )

    def test_h4_schema_resolver_key_consistency(self):
        """H4: Static check - every schema field should have a matching key in resolver output."""
        from resolvers.user_resolver import resolve_user
        schema_fields = ["id", "userName", "emailAddress", "firstName", "lastName", "createdAt"]

        resolver_result = resolve_user(None, None, id="1")
        for field in schema_fields:
            assert field in resolver_result, (
                f"Schema field '{field}' not found in resolver output keys: "
                f"{list(resolver_result.keys())}"
            )

    def test_h5_batch_query_all_non_null(self):
        """H5: Batch query - all 5 users should have non-null userName and emailAddress."""
        from app import execute_query
        query = 'query { users { id userName emailAddress } }'
        result = execute_query(query, {})
        users = result["data"]["users"]

        assert len(users) == 5, f"Expected 5 users, got {len(users)}"
        for user in users:
            assert user["userName"] is not None, f"User {user['id']}: userName is null"
            assert user["emailAddress"] is not None, f"User {user['id']}: emailAddress is null"
