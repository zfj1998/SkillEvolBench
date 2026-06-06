"""Outcome verifier for E1-LS5-T1: four-file-conflict-with-import-chain."""
import sys
import os
import subprocess
import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")
sys.path.insert(0, PROJECT_DIR)


# ============================================================
# PUBLIC TESTS (2)
# ============================================================

class TestPublic:
    def test_no_conflict_markers(self):
        """No conflict markers should remain in any file."""
        for fname in ["utils.py", "routes.py", "services.py", "public_tests/test_utils.py"]:
            fpath = os.path.join(PROJECT_DIR, fname)
            with open(fpath) as f:
                content = f.read()
            assert "<<<<<<<" not in content, f"{fname} still has conflict markers"
            assert "=======" not in content, f"{fname} still has conflict markers"
            assert ">>>>>>>" not in content, f"{fname} still has conflict markers"

    def test_test_utils_uses_new_helper_name(self):
        with open(os.path.join(PROJECT_DIR, "public_tests/test_utils.py")) as f:
            content = f.read()
        assert "process_data" in content
        assert "helper_func" not in content

    def test_basic_import_and_call(self):
        """Basic import and function call should work."""
        from utils import process_data
        result = process_data(["hello"])
        assert result == ["HELLO"]


# ============================================================
# HIDDEN TESTS (4)
# ============================================================

class TestHidden:
    def test_h1_new_name_with_default_mode(self):
        """H1: process_data(x, mode='default') should work."""
        from utils import process_data
        result = process_data(["hello", "world"], mode="default")
        assert result == ["HELLO", "WORLD"]

    def test_h2_new_name_with_custom_mode(self):
        """H2: process_data(x, mode='strict') should filter short items."""
        from utils import process_data
        result = process_data(["hi", "hello", "yo"], mode="strict")
        assert result == ["HELLO"]

    def test_h3_routes_uses_process_data(self):
        """H3: routes.py should use process_data (not helper_func)."""
        with open(os.path.join(PROJECT_DIR, "routes.py")) as f:
            content = f.read()
        assert "process_data" in content, "routes.py should use process_data"
        assert "helper_func" not in content, "routes.py should not use helper_func"

    def test_h4_services_uses_process_data(self):
        """H4: services.py should use process_data (not helper_func)."""
        with open(os.path.join(PROJECT_DIR, "services.py")) as f:
            content = f.read()
        assert "process_data" in content, "services.py should use process_data"
        assert "helper_func" not in content, "services.py should not use helper_func"

    def test_h5_routes_passes_request_mode(self):
        """Routes should pass the optional request mode through the call chain."""
        from routes import handle_request, handle_batch_request

        result = handle_request({"items": ["hi", "hello", "yo"], "mode": "strict"})
        assert result["processed"] == ["HELLO"]

        batch = handle_batch_request([
            {"items": ["hi", "hello"], "mode": "strict"},
            {"items": ["", "world"], "mode": "lenient"},
        ])
        assert batch["batches"][0] == ["HELLO"]
        assert batch["batches"][1] == ["N/A", "WORLD"]

    def test_h6_service_uses_strict_mode(self):
        """DataService.process should preserve the strict service behavior."""
        from services import DataService

        assert DataService().process(["hi", "hello", "yo"], use_cache=False) == ["HELLO"]
