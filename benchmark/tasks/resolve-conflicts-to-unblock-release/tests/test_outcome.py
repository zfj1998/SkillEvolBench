"""Outcome verifier for E1-LS5-T4: resolve-conflicts-to-unblock-release."""
import sys
import os
import json
import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")
sys.path.insert(0, PROJECT_DIR)


class TestHidden:
    def test_h1_no_conflict_markers(self):
        """H1: No conflict markers in any file."""
        for fname in ["src/auth.py", "package.json", "CHANGELOG.md"]:
            fpath = os.path.join(PROJECT_DIR, fname)
            with open(fpath) as f:
                content = f.read()
            assert "<<<<<<<" not in content, f"{fname} has conflict markers"
            assert ">>>>>>>" not in content, f"{fname} has conflict markers"

    def test_h2_all_tests_pass(self):
        """H2: All auth tests should pass."""
        from src.auth import authenticate

        # Basic auth
        result = authenticate("admin", "admin123")
        assert result["success"] is True

        # Remember me
        result = authenticate("admin", "admin123", remember_me=True)
        assert result["success"] is True
        assert result.get("remember_me") is True

    def test_h3_version_is_2_1_0(self):
        """H3: Version should be 2.1.0."""
        pkg_path = os.path.join(PROJECT_DIR, "package.json")
        with open(pkg_path) as f:
            pkg = json.load(f)
        assert pkg["version"] == "2.1.0", f"Version should be 2.1.0, got {pkg['version']}"

    def test_h4_changelog_has_v2_1_0(self):
        """H4: CHANGELOG should have v2.1.0 entry."""
        cl_path = os.path.join(PROJECT_DIR, "CHANGELOG.md")
        with open(cl_path) as f:
            content = f.read()
        assert "2.1.0" in content, "CHANGELOG should mention v2.1.0"
        # Should also keep v2.0.1 hotfix info
        assert "2.0.1" in content, "CHANGELOG should preserve v2.0.1 entry"
