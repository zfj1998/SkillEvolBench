"""Helpers for reconciliation diagnostics."""


def build_reconciliation_trace(order_id, api_total, db_total):
    return {
        "order_id": order_id,
        "api_total": str(api_total),
        "db_total": str(db_total),
    }
