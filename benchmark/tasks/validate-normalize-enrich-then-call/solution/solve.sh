#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))

fallback = root / "fallback_policy.py"
text = fallback.read_text(encoding="utf-8")
text = text.replace(
    '    if merged.get("currency") is None:\n'
    '        merged["currency"] = SYSTEM_DEFAULTS["currency"]\n',
    '    if merged.get("currency") is None:\n'
    '        merged["currency"] = SYSTEM_DEFAULTS["currency"]\n'
    '    if not merged.get("timezone"):\n'
    '        merged["timezone"] = SYSTEM_DEFAULTS["timezone"]\n',
)
fallback.write_text(text, encoding="utf-8")

transactions = root / "transactions.py"
transactions.write_text(
    '''import json
from pathlib import Path

import mock_transaction_api
from fallback_policy import fill_system_defaults
from mock_profile_api import TRACE as PROFILE_TRACE, get_profile
from normalization_policy import normalize_currency
from profile_merge import merge_profile
from transaction_contract import REQUIRED_FIELDS

DEFAULT_TIMEZONE = "UTC"


def validate_record(record):
    missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in record]
    if missing:
        raise ValueError(missing)
    return []


def enrich(record):
    try:
        profile = get_profile(record["user_id"])
    except KeyError:
        profile = {}
    merged = merge_profile(record, profile)
    if not merged.get("timezone"):
        merged["timezone"] = DEFAULT_TIMEZONE
    return fill_system_defaults(merged)


def normalize(record):
    return normalize_currency(record)


def process_transactions(path):
    PROFILE_TRACE.clear()
    mock_transaction_api.TRACE.clear()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    results = []
    for record in payload:
        validate_record(record)
        enriched = enrich(record)
        normalized = normalize(enriched)
        results.append(mock_transaction_api.send_transaction(normalized))
    return {"results": results, "profile_trace": list(PROFILE_TRACE), "tx_trace": list(mock_transaction_api.TRACE)}
''',
    encoding="utf-8",
)
PY
