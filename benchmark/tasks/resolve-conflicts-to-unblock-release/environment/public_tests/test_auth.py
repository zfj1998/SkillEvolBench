"""Authentication tests."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.auth import authenticate


def test_valid_login():
    result = authenticate("admin", "admin123")
    assert result["success"] is True
    assert "token" in result


def test_invalid_login():
    result = authenticate("admin", "wrong")
    assert result["success"] is False


def test_remember_me():
    result = authenticate("admin", "admin123", remember_me=True)
    assert result["success"] is True
    assert result.get("remember_me") is True


def test_rate_limit():
    # Rate limiting should not block normal requests
    result = authenticate("admin", "admin123")
    assert result["success"] is True
