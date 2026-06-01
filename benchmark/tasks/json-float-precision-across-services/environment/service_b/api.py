"""Service B API - runs reconciliation."""
from service_a.api import get_order_calculation, get_all_calculations
from service_b.reconciler import reconcile_order, reconcile_all


def run_single_reconciliation(order_id):
    """Run reconciliation for a single order."""
    api_json, status = get_order_calculation(order_id)
    if status != 200:
        return {"id": order_id, "status": "ERROR", "reason": "API call failed"}
    return reconcile_order(api_json)


def run_full_reconciliation():
    """Run reconciliation for all orders."""
    api_json, status = get_all_calculations()
    if status != 200:
        return {"status": "ERROR", "reason": "API call failed"}
    return reconcile_all(api_json)
