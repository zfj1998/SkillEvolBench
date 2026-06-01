"""Service B reconciler - compares API totals against database records."""
import json
from decimal import Decimal
from service_b.audit_log import build_reconciliation_trace
from service_b.comparison_policy import normalize_api_total
from shared.models import get_order


def reconcile_order(api_response_json):
    """Reconcile an API calculation against the DB record."""
    api_data = json.loads(api_response_json)
    order_id = api_data["id"]
    db_order = get_order(order_id)

    if not db_order:
        return {"id": order_id, "status": "ERROR", "reason": "Order not found in DB"}

    api_total = normalize_api_total(api_data["calculated_total"])
    db_total = db_order["total"]

    if api_total != db_total:
        trace = build_reconciliation_trace(order_id, api_total, db_total)
        return {
            "id": order_id,
            "status": "MISMATCH",
            "api_total": trace["api_total"],
            "db_total": trace["db_total"],
        }
    return {"id": order_id, "status": "MATCH"}


def reconcile_all(api_responses_json):
    """Reconcile all orders."""
    api_data_list = json.loads(api_responses_json)
    results = []
    for api_data in api_data_list:
        single_json = json.dumps(api_data)
        results.append(reconcile_order(single_json))

    mismatches = [r for r in results if r["status"] == "MISMATCH"]
    return {
        "total": len(results),
        "matches": len([r for r in results if r["status"] == "MATCH"]),
        "mismatches": len(mismatches),
        "mismatch_details": mismatches,
    }
