from __future__ import annotations

import importlib
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, run_checks

import client

DATA = PROJECT / "requests.json"


def _run_with(module_name: str):
    backend = importlib.import_module(module_name)
    client.backend = backend
    backend.TRACE.clear()
    return client.process_requests(DATA)


def _local_validate_exists():
    result = _run_with("mock_api_v1")
    assert result["failures"], "invalid input was not rejected locally"
    assert len(result["trace"]) == len(result["successes"]), (
        "invalid requests reached the remote API"
    )
    return "invalid requests are blocked locally"


def _does_not_parse_remote_400_shape():
    result = _run_with("mock_api_v2")
    assert result["successes"], "valid v2 requests should still succeed"
    return "v2 remote error shape does not break the client"


def _error_objects_local():
    failures = _run_with("mock_api_v2")["failures"]
    assert failures and all(
        {"field", "message", "source"} <= set(item)
        and item["source"] == "local-validation"
        for item in failures
    ), failures
    return "local errors use the stable public schema"


def run():
    public = run_checks("public", [("local_validate_exists", _local_validate_exists)])
    hidden = run_checks(
        "hidden",
        [
            ("does_not_parse_remote_400_shape", _does_not_parse_remote_400_shape),
            ("error_objects_local", _error_objects_local),
        ],
    )
    return emit_report("E2-LS1-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
