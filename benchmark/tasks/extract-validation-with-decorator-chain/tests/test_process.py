from __future__ import annotations

import ast
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


def _route_paths():
    routes = PROJECT / "routes"
    return [routes / name for name in ["users.py", "products.py", "orders.py", "reviews.py"]]


def _decorated_handlers():
    count = 0
    for path in _route_paths():
        module = ast.parse(read_text(path))
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.decorator_list:
                count += 1
    assert count >= 4, f"expected decorators on handlers, found {count}"
    return {"decorated_handlers": count}


def _shared_validator_exists():
    shared = read_text(PROJECT / "routes" / "shared.py")
    assert "wrapper" in shared or "validator" in shared or "schema" in shared or "decorator" in shared, "shared validation abstraction missing"
    return "shared abstraction detected"


def _route_files_are_not_full_of_bad_request_calls():
    total = 0
    for path in _route_paths():
        total += read_text(path).count("bad_request(")
    assert total <= 6, f"too many inline bad_request calls remain: {total}"
    return {"bad_request_calls": total}


def run():
    public = run_checks("public", [("decorated_handlers", _decorated_handlers)])
    hidden = run_checks(
        "hidden",
        [
            ("shared_validator_exists", _shared_validator_exists),
            ("inline_validation_reduced", _route_files_are_not_full_of_bad_request_calls),
        ],
    )
    return emit_report("E1-LS3-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
