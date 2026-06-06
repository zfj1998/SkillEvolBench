from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"


def run():
    validator = read_text(PROJECT / "record_validator.py")
    merge_policy = read_text(PROJECT / "merge_policy.py")
    public = run_checks("public", [
        ("validates_price", lambda: "price >= 0" in validator or (_ for _ in ()).throw(AssertionError("price validation missing"))),
    ])
    hidden = run_checks("hidden", [
        ("validates_name_presence", lambda: "\"name\"" in validator or (_ for _ in ()).throw(AssertionError("name field is not validated"))),
        ("uses_per_record_backup", lambda: "record[\"id\"] in invalid_ids" in merge_policy or (_ for _ in ()).throw(AssertionError("merge is not per-record"))),
        ("fallback_trigger_present", lambda: "fetch_backup(" in merge_policy or (_ for _ in ()).throw(AssertionError("backup fetch not used in merge"))),
    ])
    return emit_report("E2-LS5-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
