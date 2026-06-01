"""Money helpers shared by both services."""
from decimal import Decimal


def as_decimal(value):
    return Decimal(str(value))


def decimal_text(value):
    return format(as_decimal(value), "f")
