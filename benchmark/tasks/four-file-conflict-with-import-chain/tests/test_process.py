"""Process verifier for E1-LS5-T1."""
import os
import sys

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")
sys.path.insert(0, PROJECT_DIR)


class TestProcess:
    def test_p1_function_named_process_data(self):
        """P1: Function should be named process_data (rename preserved)."""
        with open(os.path.join(PROJECT_DIR, "utils.py")) as f:
            content = f.read()
        assert "def process_data" in content

    def test_p2_function_has_mode_parameter(self):
        """P2: Function should have mode parameter (new feature preserved)."""
        with open(os.path.join(PROJECT_DIR, "utils.py")) as f:
            content = f.read()
        assert "mode" in content

    def test_p3_all_files_consistent(self):
        """P3: All 4 files should use new name + new parameter."""
        for fname in ["utils.py", "routes.py", "services.py", "public_tests/test_utils.py"]:
            with open(os.path.join(PROJECT_DIR, fname)) as f:
                content = f.read()
            assert "process_data" in content, f"{fname} missing process_data"
            assert "helper_func" not in content, f"{fname} still uses helper_func"

    def test_p4_call_sites_pass_mode(self):
        """P4: route and service call sites should pass mode explicitly."""
        with open(os.path.join(PROJECT_DIR, "routes.py")) as f:
            routes = f.read()
        with open(os.path.join(PROJECT_DIR, "services.py")) as f:
            services = f.read()
        assert 'request_data.get("mode"' in routes or "request_data.get('mode'" in routes
        assert "mode=mode" in routes
        assert 'mode="strict"' in services or "mode='strict'" in services
