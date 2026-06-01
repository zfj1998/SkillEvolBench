"""API route handlers."""
import json
from api.serializers import serialize_order
from services.order_service import get_order, list_orders


def handle_get_order(order_id):
    """GET /api/orders/<id>"""
    order = get_order(order_id)
    if not order:
        return json.dumps({"error": "Order not found"}), 404
    return json.dumps(serialize_order(order)), 200


def handle_list_orders():
    """GET /api/orders"""
    orders = list_orders()
    return json.dumps([serialize_order(order) for order in orders]), 200
