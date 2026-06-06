from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
FETCH = PROJECT / "fetch_products.py"
CONTRACT = PROJECT / "catalog_contract.py"


def run():
    public = run_checks("public", [
        ("checks_data_presence", lambda: ("\"data\" in payload" in read_text(CONTRACT) or "payload.get(\"data\")" in read_text(CONTRACT)) or (_ for _ in ()).throw(AssertionError("no data-field validation found"))),
    ])
    hidden = run_checks("hidden", [
        ("has_fallback_strategy", lambda: ("missing data" in read_text(FETCH).lower() or "continue" in read_text(FETCH)) or (_ for _ in ()).throw(AssertionError("no safe fallback strategy found"))),
        ("does_not_replay_last_good_batch", lambda: "last_good_batch(" not in read_text(CONTRACT) or (_ for _ in ()).throw(AssertionError("still replays stale cached batches"))),
        ("does_not_blindly_trust_status", lambda: ("status" in read_text(CONTRACT) and "data" in read_text(CONTRACT)) or (_ for _ in ()).throw(AssertionError("contract validation is too shallow"))),
    ])
    return emit_report("E2-LS5-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
