from __future__ import annotations

from field_rules import AMOUNT_FIELDS, STRING_FIELDS


def infer_value(key: str, value: str):
    value = value.strip()
    if key in STRING_FIELDS:
        return value
    if key in AMOUNT_FIELDS:
        # BUG: starter still relies on direct float conversion and misses thousands separators.
        return float(value)
    return value
