"""Order total calculator for Service A."""
from service_a.serialization import build_order_payload


def calculate_order_total(quantity, unit_price):
    """Calculate order total using float arithmetic."""
    return float(quantity) * float(unit_price)


def recalculate_order(order):
    """Recalculate an order's total for verification."""
    return build_order_payload(
        order,
        calculate_order_total(order["quantity"], order["unit_price"]),
    )
