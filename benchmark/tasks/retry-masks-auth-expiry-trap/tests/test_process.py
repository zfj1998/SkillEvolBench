from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, run_checks

from auth_client import get_protected_data
from mock_auth_api import AuthAPI, FakeClock


def _expired_run():
    api = AuthAPI()
    clock = FakeClock()
    result = get_protected_data(api, clock, pre_request_delay=1.1)
    return result, api


def _distinguishes_401_and_503():
    expired_result, expired_api = _expired_run()
    retry_api = AuthAPI(transient_503_remaining=1)
    retry_result = get_protected_data(retry_api, FakeClock())
    assert expired_result["data"] == retry_result["data"] == "secret"
    assert any(row.get("status") == 401 for row in expired_api.trace)
    assert any(row.get("status") == 503 for row in retry_api.trace)
    return "401 refresh and 503 retry both work"


def _has_refresh_logic():
    result, api = _expired_run()
    assert result["token"] == "token-2"
    assert sum(row["op"] == "auth" for row in api.trace) == 2
    return "expired token is refreshed once"


def _checks_token_expired_reason():
    _, api = _expired_run()
    failures = [
        row for row in api.trace
        if row["op"] == "data" and row["status"] == 401
    ]
    assert len(failures) == 1, failures
    return "token-expired response is not blindly retried"


def _keeps_retry_bound():
    api = AuthAPI(transient_503_remaining=20)
    try:
        get_protected_data(api, FakeClock(), max_retries=3)
    except Exception:
        pass
    else:
        raise AssertionError("persistent 503 should surface after retry bound")
    calls = [row for row in api.trace if row["op"] == "data"]
    assert len(calls) <= 4, f"retry bound exceeded: {len(calls)} calls"
    return "503 retries are bounded"


def run():
    public = run_checks("public", [("distinguishes_401_and_503", _distinguishes_401_and_503)])
    hidden = run_checks(
        "hidden",
        [
            ("has_refresh_logic", _has_refresh_logic),
            ("checks_token_expired_reason", _checks_token_expired_reason),
            ("keeps_retry_bound", _keeps_retry_bound),
        ],
    )
    return emit_report("E2-LS2-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
