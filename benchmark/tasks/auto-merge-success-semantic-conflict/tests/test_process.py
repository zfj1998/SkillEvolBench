"""Process verifier for E1-LS5-T2."""
import os

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_agent_ran_tests_or_reviewed(self):
        """P1: Agent should have run tests or reviewed code after merge 'succeeded'."""
        # If agent found and fixed the issue, this implies they checked
        with open(os.path.join(PROJECT_DIR, "validators.py")) as f:
            content = f.read()
        # Count how many times 'def validate_input' appears
        count = content.count("def validate_input")
        has_fix = (
            "validate_email" in content or
            "validate_phone" in content or
            count <= 1  # Either renamed or merged into one
        )
        assert has_fix, (
            "Agent did not detect the semantic conflict - "
            "two functions with the same name still exist"
        )

    def test_p2_functions_have_different_names(self):
        """P2: The two validation functions should have different names."""
        with open(os.path.join(PROJECT_DIR, "validators.py")) as f:
            content = f.read()
        has_email = "def validate_email" in content
        has_phone = "def validate_phone" in content
        assert has_email and has_phone, (
            "Expected separate validate_email and validate_phone functions"
        )

    def test_p3_call_sites_updated(self):
        """P3: Call sites should be updated to use new function names."""
        with open(os.path.join(PROJECT_DIR, "app.py")) as f:
            content = f.read()
        has_email_call = "validate_email" in content
        has_phone_call = "validate_phone" in content
        assert has_email_call and has_phone_call, (
            "app.py should call validate_email for email and validate_phone for phone"
        )
