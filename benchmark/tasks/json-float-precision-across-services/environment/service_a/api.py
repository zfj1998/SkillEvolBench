"""Service A API - serves calculated order totals as JSON."""
import json
from service_a.calculator import recalculate_order
from shared.models import get_order, get_all_orders


def get_order_calculation(order_id):
    """API endpoint: return recalculated order as JSON."""
    order = get_order(order_id)
    if not order:
        return json.dumps({"error": "Not found"}), 404
    result = recalculate_order(order)
    return json.dumps(result), 200


def get_all_calculations():
    """API endpoint: return all recalculated orders as JSON."""
    orders = get_all_orders()
    results = [recalculate_order(o) for o in orders.values()]
    return json.dumps(results), 200
