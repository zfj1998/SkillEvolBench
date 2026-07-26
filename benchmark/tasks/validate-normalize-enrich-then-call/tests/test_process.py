from __future__ import annotations

import sys
import json
import tempfile
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, run_checks

import transactions
import mock_transaction_api


SOURCE = PROJECT / "transactions.py"


def _pipeline_order_present():
    calls = []
    originals = {
        name: getattr(transactions, name)
        for name in ("validate_record", "enrich", "normalize")
    }
    original_direct_send = getattr(transactions, "send_transaction", None)
    original_module_send = mock_transaction_api.send_transaction

    def validate(record):
        calls.append("validate")
        return []

    def enrich(record):
        calls.append("enrich")
        return dict(record, timezone="UTC", currency="USD")

    def normalize(record):
        calls.append("normalize")
        return record

    def send(record):
        calls.append("call")
        return {"status": "ok", "payload": record}

    try:
        transactions.validate_record = validate
        transactions.enrich = enrich
        transactions.normalize = normalize
        if original_direct_send is not None:
            transactions.send_transaction = send
        mock_transaction_api.send_transaction = send
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.json"
            path.write_text(json.dumps([{"user_id": "probe", "amount": 1}]), encoding="utf-8")
            transactions.process_transactions(path)
    finally:
        for name, value in originals.items():
            setattr(transactions, name, value)
        if original_direct_send is not None:
            transactions.send_transaction = original_direct_send
        mock_transaction_api.send_transaction = original_module_send
    assert calls == ["validate", "enrich", "normalize", "call"], f"wrong pipeline order: {calls}"
    return "runtime pipeline order is validate -> enrich -> normalize -> call"


def _fallback_for_null_timezone():
    enriched = transactions.enrich({"user_id": "u2", "amount": 10, "currency": "EUR"})
    assert enriched.get("timezone") == "UTC", f"null timezone fallback failed: {enriched!r}"
    return "null timezone falls back to UTC"


def _fallback_for_missing_profile():
    enriched = transactions.enrich({"user_id": "u3", "amount": 10, "currency": "EUR"})
    assert enriched.get("timezone") == "UTC" and enriched.get("currency"), enriched
    return "missing profile uses system defaults"


def _explicit_utc_present():
    enriched = transactions.enrich({"user_id": "u2", "amount": 10, "currency": "EUR"})
    assert enriched["timezone"] == "UTC"
    return "UTC fallback observed"


def run():
    public = run_checks("public", [("pipeline_order_present", _pipeline_order_present)])
    hidden = run_checks(
        "hidden",
        [
            ("fallback_for_null_timezone", _fallback_for_null_timezone),
            ("fallback_for_missing_profile", _fallback_for_missing_profile),
            ("explicit_utc_present", _explicit_utc_present),
        ],
    )
    return emit_report("E2-LS1-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
