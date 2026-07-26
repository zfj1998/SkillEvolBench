from __future__ import annotations

import sys
import json
import tempfile
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from mock_profile_api import PROFILES, TRACE as PROFILE_TRACE
from mock_transaction_api import TRACE as TX_TRACE
from transactions import enrich, normalize, process_transactions, validate_record
from verifier_lib.runtime import emit_report, print_report, run_checks


DATA = PROJECT / "requests.json"


def _expect_local_validation_error():
    try:
        validate_record({"user_id": "u1"})
    except ValueError:
        return "missing amount rejected locally"
    raise AssertionError("missing required amount should fail local validation")


def _process_return_contract():
    result = process_transactions(DATA)
    required = {"results", "profile_trace", "tx_trace"}
    if required <= set(result):
        return "process return contract present"
    raise AssertionError(f"missing process return keys: {required - set(result)}")


def _missing_profile_uses_defaults():
    result = process_transactions(DATA)
    payloads = [item["payload"] for item in result["results"]]
    u3 = next(item for item in payloads if item["user_id"] == "u3")
    assert u3["timezone"] == "UTC"
    assert u3["currency"] == "USD"
    return "missing profile uses UTC/USD system defaults"


def _validation_happens_before_calls():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "invalid.json"
        path.write_text(json.dumps([{"user_id": "u1"}]), encoding="utf-8")
        try:
            process_transactions(path)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid record should fail locally")
    assert PROFILE_TRACE == [], f"profile API was called before validation: {PROFILE_TRACE!r}"
    assert TX_TRACE == [], f"transaction API was called before validation: {TX_TRACE!r}"
    return "invalid input rejected before both APIs"


def run():
    public = run_checks(
        "public",
        [
            ("profile_enrichment_for_complete_user", lambda: enrich({"user_id": "u1", "amount": 10, "currency": "USD"})["timezone"] == PROFILES["u1"]["timezone"] or (_ for _ in ()).throw(AssertionError("u1 timezone should come from profile"))),
            ("eur_normalizes_to_usd", lambda: normalize({"user_id": "u2", "amount": 10, "currency": "EUR"})["currency"] == "USD" or (_ for _ in ()).throw(AssertionError("EUR should normalize to USD"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("missing_amount_rejected_locally", lambda: _expect_local_validation_error()),
            ("null_timezone_fallback", lambda: enrich({"user_id": "u2", "amount": 10, "currency": "EUR"}).get("timezone") == "UTC" or (_ for _ in ()).throw(AssertionError("null timezone should fall back to UTC"))),
            ("missing_profile_fallback", _missing_profile_uses_defaults),
            ("final_payloads_normalized", lambda: (process_transactions(DATA), all(item["currency"] == "USD" and item.get("timezone") for item in TX_TRACE))[-1] or (_ for _ in ()).throw(AssertionError(f"final payloads must be normalized, got {TX_TRACE!r}"))),
            ("process_return_contract", _process_return_contract),
            ("validation_precedes_api_calls", _validation_happens_before_calls),
        ],
    )
    return emit_report("E2-LS1-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
