"""Record transformer module - applies business transformations."""
from formatting_policy import format_currency


def transform_record(record):
    """Apply business transformations to a record."""
    record["amount_formatted"] = format_currency(record["amount"])
    record["processed"] = True
    return record


def transform_batch(records):
    """Transform a batch of records."""
    return [transform_record(dict(r)) for r in records]
