"""Shared helpers for ETL amount tracing."""


def snapshot_amount(record):
    return {
        "id": record["id"],
        "amount_type": type(record["amount"]).__name__,
        "amount_text": str(record["amount"]),
    }


def attach_snapshot(record):
    record["amount_snapshot"] = snapshot_amount(record)
    return record
