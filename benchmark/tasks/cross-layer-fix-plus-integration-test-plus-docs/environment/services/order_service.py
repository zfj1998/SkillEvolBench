"""Order business logic service."""
from database.queries import get_order_by_id, get_all_orders
from services.price_policy import normalize_display_amount


def get_order(order_id):
    """Get a single order."""
    order = get_order_by_id(order_id)
    if not order:
        return None
    order["total_amount"] = normalize_display_amount(order["total_amount"])
    return order


def list_orders():
    """List all orders."""
    orders = get_all_orders()
    for order in orders:
        order["total_amount"] = normalize_display_amount(order["total_amount"])
    return orders


def calculate_order_total(order_id):
    """Recalculate an order's total."""
    order = get_order_by_id(order_id)
    if not order:
        return None
    return order["items_count"] * order["unit_price"]
