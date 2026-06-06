"""Process verifier for E1-LS5-T5."""
import os
import re

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_all_sql_parameterized(self):
        """P1: All SQL queries should use parameterized queries."""
        db_path = os.path.join(PROJECT_DIR, "database.py")
        with open(db_path) as f:
            source = f.read()

        fstring_sql = re.findall(r'execute\s*\(\s*f["\']', source)
        assert len(fstring_sql) == 0, (
            "Found f-string SQL queries - all should be parameterized"
        )

    def test_p2_search_function_exists(self):
        """P2: Search feature should be preserved."""
        db_path = os.path.join(PROJECT_DIR, "database.py")
        with open(db_path) as f:
            source = f.read()
        assert "def search_users" in source, "Search function should exist"

    def test_p3_detect_accept_ours(self):
        """P3: Detect if accept-ours was used (lost security fix)."""
        db_path = os.path.join(PROJECT_DIR, "database.py")
        with open(db_path) as f:
            source = f.read()

        # If get_user_by_id still uses f-string, accept-ours was likely used
        # (security fix was in get_user_by_id)
        has_fstring_get_user = 'f"SELECT * FROM users WHERE id = {' in source
        assert not has_fstring_get_user, (
            "get_user_by_id still uses f-string SQL - "
            "security fix was lost (accept-ours detected)"
        )
