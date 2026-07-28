from __future__ import annotations

from pathlib import Path

import sys

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"

if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from merge_policy import merge_records
from record_validator import is_valid_record
from verifier_lib.runtime import emit_report, print_report, run_checks


def run():
    valid = {
        "id": 1, "name": "Widget", "price": 10, "currency": "USD",
        "in_stock": True, "updated_at": "2026-04-12T10:00:00Z",
    }
    public = run_checks("public", [
        ("validates_price", lambda: not is_valid_record({**valid, "price": -1}) or (_ for _ in ()).throw(AssertionError("negative price accepted"))),
    ])
    hidden = run_checks("hidden", [
        ("validates_name_presence", lambda: not is_valid_record({key: value for key, value in valid.items() if key != "name"}) and not is_valid_record({**valid, "name": None}) or (_ for _ in ()).throw(AssertionError("missing/null name accepted"))),
        ("uses_per_record_backup", lambda: merge_records([valid, {**valid, "id": 2}], {2}, lambda item_id: {**valid, "id": item_id, "name": "backup"}) == [valid, {**valid, "id": 2, "name": "backup"}] or (_ for _ in ()).throw(AssertionError("merge is not per-record"))),
        ("fallback_trigger_present", lambda: merge_records([valid], {1}, lambda item_id: {**valid, "name": "backup"})[0]["name"] == "backup" or (_ for _ in ()).throw(AssertionError("backup fetch not used in merge"))),
    ])
    return emit_report("E2-LS5-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
