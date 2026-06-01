"""Shared order model and simulated database."""
from decimal import Decimal

ORDERS_DB = {
    "ORD001": {"id": "ORD001", "item": "Widget A", "quantity": 3,
               "unit_price": Decimal("0.10"), "total": Decimal("0.30")},
    "ORD002": {"id": "ORD002", "item": "Widget B", "quantity": 1,
               "unit_price": Decimal("100.00"), "total": Decimal("100.00")},
    "ORD003": {"id": "ORD003", "item": "Widget C", "quantity": 7,
               "unit_price": Decimal("14.28"), "total": Decimal("99.96")},
    "ORD004": {"id": "ORD004", "item": "Widget D", "quantity": 1,
               "unit_price": Decimal("999999.99"), "total": Decimal("999999.99")},
    "ORD005": {"id": "ORD005", "item": "Widget E", "quantity": 2,
               "unit_price": Decimal("25.05"), "total": Decimal("50.10")},
}


def get_order(order_id):
    """Get an order by ID."""
    order = ORDERS_DB.get(order_id)
    return dict(order) if order else None


def get_all_orders():
    """Get all orders."""
    return {k: dict(v) for k, v in ORDERS_DB.items()}
