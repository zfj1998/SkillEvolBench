from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

INVALID_NULLS = {"", "na", "n/a", "null", "none"}


def normalize_date(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("/", "-")
    if not text:
        return None
    try:
        dt = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
    if dt.year == 2024 and dt.month == 3:
        return dt.isoformat()
    return None


def parse_amount(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in INVALID_NULLS:
        return None
    if text.startswith("$"):
        text = text[1:].strip()
    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def parse_quantity(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None
