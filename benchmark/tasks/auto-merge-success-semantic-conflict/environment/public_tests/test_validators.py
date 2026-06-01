"""Tests for validators."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from validators import validate_input, validate_name, validate_age


class TestEmailValidation:
    def test_valid_email(self):
        result = validate_input("alice@example.com")
        assert result["valid"] is True
        assert result["type"] == "email"

    def test_invalid_email(self):
        result = validate_input("not-an-email")
        assert result["valid"] is False


class TestPhoneValidation:
    def test_valid_phone(self):
        result = validate_input("1234567890")
        assert result["valid"] is True
        assert result["type"] == "phone"

    def test_valid_phone_formatted(self):
        result = validate_input("+1 (234) 567-8900")
        assert result["valid"] is True


class TestNameValidation:
    def test_valid_name(self):
        result = validate_name("Alice")
        assert result["valid"] is True


class TestAgeValidation:
    def test_valid_age(self):
        result = validate_age(25)
        assert result["valid"] is True
