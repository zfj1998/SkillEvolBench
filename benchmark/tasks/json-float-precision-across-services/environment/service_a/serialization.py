"""Serialization helpers for service A payloads."""


def build_order_payload(order, calculated_total):
    return {
        "id": order["id"],
        "item": order["item"],
        "quantity": order["quantity"],
        "unit_price": float(order["unit_price"]),
        "calculated_total": calculated_total,
    }
