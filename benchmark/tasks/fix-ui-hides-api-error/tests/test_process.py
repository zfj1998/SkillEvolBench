"""Process verifier for E1-LS4-T5: fix-ui-hides-api-error."""
import os

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_services_modified(self):
        """P1: services.py should be modified to remove catch-all exception handler."""
        path = os.path.join(PROJECT_DIR, "backend", "services.py")
        with open(path) as f:
            source = f.read()
        # The bare "except Exception:" catch-all should be replaced
        assert "except Exception:" not in source or "raise" in source, (
            "services.py still has a catch-all 'except Exception:' that swallows errors"
        )

    def test_p2_frontend_modified(self):
        """P2: UserProfile.jsx should be modified to show error messages."""
        path = os.path.join(PROJECT_DIR, "frontend", "UserProfile.jsx")
        with open(path) as f:
            source = f.read()
        # Should distinguish between error and no-data states
        checks_status = "status" in source and "error" in source.lower()
        checks_response = "response.ok" in source or "response.status" in source
        assert checks_status or checks_response, (
            "Frontend should check response status to distinguish errors from no-data"
        )

    def test_p3_not_frontend_only_fix(self):
        """P3: Fix should NOT be frontend-only. Backend must also be modified."""
        services_path = os.path.join(PROJECT_DIR, "backend", "services.py")
        routes_path = os.path.join(PROJECT_DIR, "backend", "routes.py")

        with open(services_path) as f:
            services_src = f.read()
        with open(routes_path) as f:
            routes_src = f.read()

        # Backend should return proper HTTP status codes
        backend_modified = (
            "500" in routes_src or
            "raise" in services_src or
            "ConnectionError" in services_src
        )
        assert backend_modified, (
            "Backend was not modified - frontend-only fix detected. "
            "Backend should return 500 on server errors."
        )

    def test_p4_specific_exception_handling(self):
        """P4: except Exception should be replaced with specific exception types."""
        path = os.path.join(PROJECT_DIR, "backend", "services.py")
        with open(path) as f:
            source = f.read()

        has_bare_except = "except Exception:" in source and "raise" not in source
        has_specific = "except ConnectionError" in source or "except (ConnectionError" in source

        assert not has_bare_except or has_specific, (
            "services.py should use specific exception types instead of bare 'except Exception:'"
        )
