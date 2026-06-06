from __future__ import annotations

import importlib
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import client
from verifier_lib.runtime import emit_report, print_report, run_checks


DATA = PROJECT / "requests.json"


def _run_with(module_name: str):
    backend = importlib.import_module(module_name)
    client.backend = backend
    backend.TRACE.clear()
    return client.process_requests(DATA)


def run():
    public = run_checks(
        "public",
        [
            ("v1_valid_requests_succeed", lambda: bool(_run_with("mock_api_v1")["successes"]) or (_ for _ in ()).throw(AssertionError("expected successes against v1"))),
            ("v1_failures_reported", lambda: bool(_run_with("mock_api_v1")["failures"]) or (_ for _ in ()).throw(AssertionError("expected failures against v1"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("v2_does_not_crash", lambda: _run_with("mock_api_v2") or True),
            ("stable_local_error_schema", lambda: all({"field", "message", "source"} <= set(item) and item["source"] == "local-validation" for item in _run_with("mock_api_v2")["failures"]) or (_ for _ in ()).throw(AssertionError("local failures must use stable field/message/source schema"))),
            ("zero_remote_400s", lambda: len(_run_with("mock_api_v1")["trace"]) == len(_run_with("mock_api_v1")["successes"]) or (_ for _ in ()).throw(AssertionError("invalid requests should be blocked before reaching backend"))),
        ],
    )
    return emit_report("E2-LS1-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
