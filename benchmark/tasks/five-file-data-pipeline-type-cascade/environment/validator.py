"""Record validator module - validates and normalizes records."""
from amount_audit import attach_snapshot


def validate_record(record):
    """Validate a single record. Returns the validated record."""
    if not record.get("id"):
        raise ValueError("Record missing id")
    if not record.get("name"):
        raise ValueError("Record missing name")
    if record.get("amount") is None:
        raise ValueError("Record missing amount")

    attach_snapshot(record)
    # Normalize amount to float for consistent handling
    record["amount"] = float(record["amount"])

    return record


def validate_batch(records):
    """Validate a batch of records."""
    validated = []
    for record in records:
        try:
            validated.append(validate_record(record))
        except ValueError as e:
            print(f"Validation error for record {record.get('id', '?')}: {e}")
    return validated
