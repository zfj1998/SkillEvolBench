from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from auth_client import get_protected_data
from mock_auth_api import AuthAPI, FakeClock
from verifier_lib.runtime import emit_report, print_report, run_checks


def _run_initial_success():
    api = AuthAPI()
    clock = FakeClock()
    return get_protected_data(api, clock), api


def _run_expired_then_refresh():
    api = AuthAPI()
    clock = FakeClock()
    return get_protected_data(api, clock, pre_request_delay=1.1), api


def _run_503_retry():
    api = AuthAPI(transient_503_remaining=1)
    clock = FakeClock()
    return get_protected_data(api, clock), api


def _run_refresh_failure():
    api = AuthAPI(refresh_fail=True)
    clock = FakeClock()
    try:
        get_protected_data(api, clock, pre_request_delay=1.1)
    except Exception:
        return True
    raise AssertionError("refresh failure should surface as an error")


def run():
    public = run_checks(
        "public",
        [
            ("initial_fetch_succeeds", lambda: _run_initial_success()[0]["data"] == "secret" or (_ for _ in ()).throw(AssertionError("expected protected data"))),
            ("invalid_token_is_rejected", lambda: AuthAPI().fetch_data("bogus", FakeClock())["status"] == 401 or (_ for _ in ()).throw(AssertionError("invalid token should be rejected"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("expired_token_refreshes_and_succeeds", lambda: _run_expired_then_refresh()[0]["data"] == "secret" or (_ for _ in ()).throw(AssertionError("refresh path failed"))),
            ("new_token_used_after_refresh", lambda: _run_expired_then_refresh()[0]["token"] == "token-2" or (_ for _ in ()).throw(AssertionError("expected refreshed token"))),
            ("401_not_blindly_retried", lambda: len([row for row in _run_expired_then_refresh()[1].trace if row["op"] == "data" and row["status"] == 401]) == 1 or (_ for _ in ()).throw(AssertionError("401 should not be retried repeatedly"))),
            ("503_still_retried", lambda: len([row for row in _run_503_retry()[1].trace if row["op"] == "data"]) == 2 and _run_503_retry()[0]["data"] == "secret" or (_ for _ in ()).throw(AssertionError("503 retry path failed"))),
            ("refresh_failure_surfaces", _run_refresh_failure),
        ],
    )
    return emit_report("E2-LS2-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
