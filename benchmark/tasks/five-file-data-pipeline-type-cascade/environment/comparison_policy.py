"""Comparison policy for change detection."""


def has_amount_changed(current_amount, historical_amount):
    return current_amount != historical_amount
