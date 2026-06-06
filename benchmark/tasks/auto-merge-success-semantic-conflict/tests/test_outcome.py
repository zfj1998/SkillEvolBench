"""Outcome verifier for E1-LS5-T2: auto-merge-success-semantic-conflict."""
import sys
import os
import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")
sys.path.insert(0, PROJECT_DIR)


# ============================================================
# HIDDEN TESTS (4) - No public tests (merge "succeeded")
# ============================================================

class TestHidden:
    def test_h1_email_validation_exists(self):
        """H1: Email validation should exist and work correctly."""
        # Import after potential fix
        import importlib
        import validators
        importlib.reload(validators)

        # There should be a function that validates emails
        # It might be renamed to validate_email
        validate_email = getattr(validators, 'validate_email', None)
        if validate_email is None:
            # Try validate_input if it still exists and handles email
            validate_fn = getattr(validators, 'validate_input', None)
            if validate_fn:
                result = validate_fn("alice@example.com")
                assert result["valid"] is True and result.get("type") == "email", (
                    "No email validation function found"
                )
                return
            pytest.fail("No email validation function found")
            return

        result = validate_email("alice@example.com")
        assert result["valid"] is True
        assert result["type"] == "email"

    def test_h2_phone_validation_exists(self):
        """H2: Phone validation should exist and work correctly."""
        import importlib
        import validators
        importlib.reload(validators)

        validate_phone = getattr(validators, 'validate_phone', None)
        if validate_phone is None:
            validate_fn = getattr(validators, 'validate_input', None)
            if validate_fn:
                result = validate_fn("1234567890")
                assert result["valid"] is True and result.get("type") == "phone", (
                    "No phone validation function found"
                )
                return
            pytest.fail("No phone validation function found")
            return

        result = validate_phone("1234567890")
        assert result["valid"] is True
        assert result["type"] == "phone"

    def test_h3_both_importable_without_collision(self):
        """H3: Both validation functions should be importable (not same name)."""
        import importlib
        import validators
        importlib.reload(validators)

        # Check that there are two distinct validation functions
        has_email_fn = hasattr(validators, 'validate_email')
        has_phone_fn = hasattr(validators, 'validate_phone')

        # If both exist as separate functions, good
        if has_email_fn and has_phone_fn:
            assert True
            return

        # If validate_input still exists as a single function, that's a problem
        # unless it dispatches correctly
        pytest.fail(
            "Both email and phone validation should have distinct function names "
            "(e.g., validate_email and validate_phone) to avoid name collision"
        )

    def test_h4_validate_email_and_phone_each_correct(self):
        """H4: Each function should validate its own type correctly."""
        import importlib
        import validators
        importlib.reload(validators)

        validate_email = getattr(validators, 'validate_email', None)
        validate_phone = getattr(validators, 'validate_phone', None)

        if validate_email:
            # Email function should reject phone numbers
            result = validate_email("1234567890")
            assert result["valid"] is False, "validate_email should reject phone numbers"

            result = validate_email("alice@example.com")
            assert result["valid"] is True

        if validate_phone:
            # Phone function should reject emails
            result = validate_phone("alice@example.com")
            assert result["valid"] is False, "validate_phone should reject emails"

            result = validate_phone("+1 (234) 567-8900")
            assert result["valid"] is True
