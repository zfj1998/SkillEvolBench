"""Utility functions for the FinLedger platform."""


def format_currency(amount: float) -> str:
    """Format a float as a USD currency string."""
    if amount < 0:
        return f'-${abs(amount):,.2f}'
    return f'${amount:,.2f}'


def clamp_non_negative(value: float) -> float:
    """Clamp a value to be non-negative (losses → 0)."""
    return max(0.0, value)


def percentage_str(rate: float) -> str:
    """Format a rate (0.0725) as a percentage string ('7.25%')."""
    return f'{rate * 100:.2f}%'
