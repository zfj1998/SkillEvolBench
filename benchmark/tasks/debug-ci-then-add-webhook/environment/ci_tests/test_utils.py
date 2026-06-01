"""Failing CI test 3: date comparison on non-zero-padded dates."""

from app.utils import is_before


def test_is_before_handles_non_zero_padded_dates():
    assert is_before('2024-1-9', '2024-01-10') is True
