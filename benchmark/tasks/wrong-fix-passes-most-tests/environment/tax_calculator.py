"""
Tax calculator for the FinLedger platform.

Computes tax obligations for a given income and region.
Uses the rate schedule from tax_rates.py.
"""

from tax_rates import get_tax_rate
from utils import format_currency, clamp_non_negative


def calculate_tax(income: float, region: str) -> float:
    """
    Calculate the tax amount for an income in a given region.

    Args:
        income:  gross income (may be negative for loss carryforward)
        region:  two-letter state abbreviation (e.g. "CA", "TX")

    Returns:
        Tax amount as a non-negative float, rounded to 2 decimal places.

    Raises:
        ValueError: if the region is not recognized.
    """
    taxable = clamp_non_negative(income)
    rate = get_tax_rate(region)
    return round(taxable * rate, 2)


def calculate_effective_rate(income: float, region: str) -> float:
    """Return the effective tax rate (tax / income) as a percentage."""
    if income <= 0:
        return 0.0
    tax = calculate_tax(income, region)
    return round((tax / income) * 100, 4)


def calculate_net_income(income: float, region: str) -> float:
    """Return income after tax."""
    return round(income - calculate_tax(income, region), 2)
