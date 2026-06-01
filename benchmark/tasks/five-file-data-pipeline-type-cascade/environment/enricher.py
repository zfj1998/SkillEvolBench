"""Record enricher module - detects changes by comparing with historical data."""
from comparison_policy import has_amount_changed
from extractor import get_historical_amount


def enrich_record(record):
    """Enrich a record with change detection info."""
    historical = get_historical_amount(record["id"])
    if historical is not None:
        record["changed"] = has_amount_changed(record["amount"], historical)
        record["historical_amount"] = historical
    else:
        record["changed"] = True  # New record, no history
        record["historical_amount"] = None
    return record


def enrich_batch(records):
    """Enrich a batch of records."""
    return [enrich_record(dict(r)) for r in records]
