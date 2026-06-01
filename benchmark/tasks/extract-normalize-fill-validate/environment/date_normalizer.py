from __future__ import annotations


def normalize_invoice_date(date_text: str) -> str:
    # BUG: legacy pipeline still returns the raw DD/MM/YYYY string.
    return date_text
