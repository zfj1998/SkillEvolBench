"""Tax calculator tests."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from tax_calculator import calculate_tax


class TestCalculateTax:

    def test_california_100k(self):
        """CA $100,000 × 7.25% = $7,250.00"""
        assert calculate_tax(100_000, "CA") == 7250.00

    def test_california_50k(self):
        """CA $50,000 × 7.25% = $3,625.00"""
        assert calculate_tax(50_000, "CA") == 3625.00

    def test_zero_income(self):
        """Zero income → zero tax."""
        assert calculate_tax(0, "TX") == 0.0

    def test_negative_income_clamped(self):
        """Negative income (loss carryforward) → zero tax."""
        assert calculate_tax(-5000, "NY") == 0.0

    def test_invalid_region(self):
        """Unknown region should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_tax(10000, "ZZ")
