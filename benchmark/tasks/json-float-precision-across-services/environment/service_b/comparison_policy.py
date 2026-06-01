"""Comparison helpers for reconciliation service."""
from decimal import Decimal


def normalize_api_total(api_value):
    return Decimal(str(api_value))
