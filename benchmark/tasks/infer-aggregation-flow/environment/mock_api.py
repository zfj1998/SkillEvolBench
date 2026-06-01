from __future__ import annotations

from typing import Any

TRACE: list[dict[str, Any]] = []

DATA = {
    '/sales/us': {'currency': 'USD', 'sales': [{'product_line': 'hardware', 'amount': 1200.0}, {'product_line': 'software', 'amount': 800.0}]},
    '/sales/eu': {'currency': 'EUR', 'records': [{'line': 'hardware', 'revenue': 900.0}, {'line': 'services', 'revenue': 700.0}]},
    '/sales/apac': {'currency': 'JPY', 'rows': [{'product': 'software', 'total': 150000.0}, {'product': 'services', 'total': 90000.0}]},
}


def reset_state() -> None:
    TRACE.clear()


def fetch_sales(endpoint: str) -> dict[str, Any]:
    TRACE.append({'endpoint': endpoint})
    return DATA[endpoint]
