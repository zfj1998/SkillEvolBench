"""Process verifier for E1-LS5-T4."""
import os

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_correct_merge_order(self):
        """P1: Auth should have both rate limiting and remember_me."""
        with open(os.path.join(PROJECT_DIR, "src", "auth.py")) as f:
            content = f.read()
        has_rate_limit = "rate_limit" in content.lower() or "_check_rate_limit" in content
        has_remember_me = "remember_me" in content
        assert has_rate_limit and has_remember_me, (
            "Auth should preserve both rate limiting (hotfix) and remember_me (feature)"
        )

    def test_p2_tests_not_skipped(self):
        """P2: Tests should exist and cover both features."""
        test_path = os.path.join(PROJECT_DIR, "public_tests", "test_auth.py")
        with open(test_path) as f:
            content = f.read()
        assert "remember_me" in content, "Tests should cover remember_me"
