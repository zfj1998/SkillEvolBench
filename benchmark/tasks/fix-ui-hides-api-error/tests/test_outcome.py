"""Outcome verifier for E1-LS4-T5: fix-ui-hides-api-error."""
import sys
import os
import json
import pytest
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))


@contextmanager
def patched_database(replacement):
    """Patch the database dependency regardless of valid import style.

    Solutions may access ``backend.database.db`` dynamically or import that
    object into ``backend.services``.  Both designs satisfy the task, so the
    verifier patches both observable seams.
    """
    import backend.database as db_module
    import backend.services as services_module

    original_db = db_module.db
    imported_aliases = {
        name: value
        for name, value in vars(services_module).items()
        if value is original_db
    }
    db_module.db = replacement
    for name in imported_aliases:
        setattr(services_module, name, replacement)
    try:
        yield
    finally:
        db_module.db = original_db
        for name, value in imported_aliases.items():
            setattr(services_module, name, value)


# ============================================================
# PUBLIC UI TESTS (3)
# ============================================================

class TestPublicUI:
    def test_normal_display_correct(self):
        """Normal user data should be displayed correctly."""
        from backend.routes import handle_get_user
        body, status = handle_get_user(1)
        data = json.loads(body)
        if status == 200 and data.get("status") == "ok":
            assert data["data"]["name"] == "Alice Smith"

    def test_error_shows_error_message(self):
        """When there's an error, frontend should show error message, not 'No data available'."""
        # Read UserProfile.jsx and check it handles error status
        jsx_path = os.path.join(os.path.dirname(__file__), "..", "project", "frontend", "UserProfile.jsx")
        with open(jsx_path) as f:
            content = f.read()
        # Should check data.status or response.ok
        has_error_check = (
            "status" in content and ("error" in content.lower())
            or "response.ok" in content
            or "response.status" in content
        )
        has_no_data_only = "No data available" in content and "error" not in content.lower()
        assert not has_no_data_only or has_error_check, (
            "Frontend should distinguish between 'no data' and 'error'"
        )

    def test_loading_state(self):
        """Loading state should show spinner."""
        jsx_path = os.path.join(os.path.dirname(__file__), "..", "project", "frontend", "UserProfile.jsx")
        with open(jsx_path) as f:
            content = f.read()
        assert "Loading" in content or "spinner" in content


# ============================================================
# HIDDEN API TESTS (4)
# ============================================================

class TestHiddenAPI:
    def test_h1_db_error_returns_500(self):
        """H1: When database throws ConnectionError, backend should return 500 (not 200)."""
        from backend.database import DatabaseConnection
        from backend.services import get_user_profile
        from backend.routes import handle_get_user

        # Force a database error
        class FailingDB:
            def get_user(self, user_id):
                raise ConnectionError("Database connection lost")
        with patched_database(FailingDB()):
            body, status = handle_get_user(1)
            assert status == 500, (
                f"Backend should return 500 on DB error, got {status}. "
                f"Body: {body}"
            )

    def test_h2_error_response_has_meaningful_message(self):
        """H2: Error response should contain a meaningful error message."""
        from backend.routes import handle_get_user
        class FailingDB:
            def get_user(self, user_id):
                raise ConnectionError("Database connection lost")
        with patched_database(FailingDB()):
            body, status = handle_get_user(1)
            data = json.loads(body)
            error_msg = data.get("message", data.get("error", ""))
            assert len(error_msg) > 5, f"Error message should be meaningful, got: '{error_msg}'"

    def test_h3_normal_request_returns_200(self):
        """H3: Normal successful request should return 200 with data."""
        from backend.routes import handle_get_user
        class WorkingDB:
            def get_user(self, user_id):
                return {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"}
        with patched_database(WorkingDB()):
            body, status = handle_get_user(1)
            assert status == 200
            data = json.loads(body)
            assert data.get("data") is not None

    def test_h3b_missing_user_returns_404_schema(self):
        """Missing users should return the documented not_found schema."""
        from backend.routes import handle_get_user
        class WorkingDB:
            def get_user(self, user_id):
                return None
        with patched_database(WorkingDB()):
            body, status = handle_get_user(999)
            assert status == 404
            data = json.loads(body)
            assert data["status"] == "not_found"
            assert isinstance(data.get("message"), str) and data["message"]
            assert data.get("data") is None

    def test_h4_retry_after_temporary_error(self):
        """H4: After a temporary error, subsequent requests should succeed."""
        from backend.routes import handle_get_user
        call_count = [0]
        class IntermittentDB:
            def get_user(self, user_id):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise ConnectionError("Temporary failure")
                return {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"}
        with patched_database(IntermittentDB()):
            # First call may fail
            handle_get_user(1)
            # Second call should succeed
            body, status = handle_get_user(1)
            assert status == 200
            data = json.loads(body)
            assert data.get("data") is not None
