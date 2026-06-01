import json
from pathlib import Path

from fallback_policy import fill_system_defaults
from mock_profile_api import TRACE as PROFILE_TRACE, get_profile
from mock_transaction_api import TRACE as TX_TRACE, send_transaction
from normalization_policy import normalize_currency
from profile_merge import merge_profile
from transaction_contract import REQUIRED_FIELDS


def validate_record(record):
    missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in record]
    return missing


def enrich(record):
    profile = get_profile(record["user_id"])
    merged = merge_profile(record, profile)
    return fill_system_defaults(merged)


def normalize(record):
    return normalize_currency(record)


def process_transactions(path):
    PROFILE_TRACE.clear()
    TX_TRACE.clear()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    results = []
    for record in payload:
        validate_record(record)
        enriched = enrich(record)
        normalized = normalize(enriched)
        results.append(send_transaction(normalized))
    return {"results": results, "profile_trace": list(PROFILE_TRACE), "tx_trace": list(TX_TRACE)}
