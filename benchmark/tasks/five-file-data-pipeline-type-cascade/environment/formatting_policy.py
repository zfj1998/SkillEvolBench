"""Formatting helpers for downstream loader and reports."""


def format_currency(amount):
    return f"${amount:,.2f}"


def summarize_change(record):
    return {
        "id": record["id"],
        "changed": record.get("changed", False),
        "historical_amount": str(record.get("historical_amount")),
    }
