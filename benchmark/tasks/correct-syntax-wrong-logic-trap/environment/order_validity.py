from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation


def valid_order_status(value: object) -> bool:
    return str(value).strip().lower() in {"paid", "shipped"}


def parse_amount(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    return amount if amount > 0 else None


def valid_order_date(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            pass
    return False
