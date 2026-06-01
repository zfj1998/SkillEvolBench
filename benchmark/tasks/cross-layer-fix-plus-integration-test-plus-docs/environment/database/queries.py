"""Database query functions."""
from database.row_mappers import normalize_order_row
from models.order import ORDERS


def get_order_by_id(order_id):
    """Get an order by its ID."""
    order = ORDERS.get(order_id)
    return normalize_order_row(order) if order else None


def get_all_orders():
    """Get all orders."""
    return [normalize_order_row(o) for o in ORDERS.values()]
