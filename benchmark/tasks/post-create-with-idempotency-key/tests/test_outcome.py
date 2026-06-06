from __future__ import annotations

import sys
import uuid
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from mock_api import OrderAPI
from order_client import create_order
from verifier_lib.runtime import emit_report, print_report, run_checks

ORDER = {"sku": "SKU-42", "quantity": 2}


def _run_case():
    api = OrderAPI()
    order = create_order(dict(ORDER), api, max_attempts=2)
    return order, api


def _extract_key(trace):
    return trace[0]["headers"].get("Idempotency-Key")


def _key_is_uuid():
    uuid.UUID(_extract_key(_run_case()[1].trace))
    return "uuid ok"


def _same_key_reused():
    _, api = _run_case()
    key = _extract_key(api.trace)
    assert key is not None, "expected a shared idempotency key"
    assert all(row["headers"].get("Idempotency-Key") == key for row in api.trace), "expected a shared idempotency key"
    return "same key reused"


def run():
    public = run_checks(
        "public",
        [
            ("order_created", lambda: _run_case()[0]["sku"] == "SKU-42" or (_ for _ in ()).throw(AssertionError("order not created"))),
            ("order_shape_correct", lambda: _run_case()[0]["quantity"] == 2 or (_ for _ in ()).throw(AssertionError("unexpected order quantity"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
                ("same_key_used_for_all_attempts", _same_key_reused),
            ("only_one_order_created", lambda: len(_run_case()[1].orders) == 1 or (_ for _ in ()).throw(AssertionError("duplicate orders were created"))),
            ("key_is_uuid", _key_is_uuid),
            ("body_is_consistent", lambda: all(row["body"] == ORDER for row in _run_case()[1].trace) or (_ for _ in ()).throw(AssertionError("request body changed across retries"))),
            ("returned_order_is_correct", lambda: _run_case()[0]["order_id"] == "ord-1" or (_ for _ in ()).throw(AssertionError("unexpected order id"))),
        ],
    )
    return emit_report("E2-LS2-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
