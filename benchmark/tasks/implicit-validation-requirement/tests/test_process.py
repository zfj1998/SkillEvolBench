from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"


def run():
    guard = read_text(PROJECT / "transport_guard.py")
    public = run_checks("public", [
        ("json_parse_guard_present", lambda: "response.json()" in guard and "except Exception" in guard or (_ for _ in ()).throw(AssertionError("missing JSON parse guard"))),
    ])
    hidden = run_checks("hidden", [
        ("empty_data_handled", lambda: "len(data) == 0" in guard or (_ for _ in ()).throw(AssertionError("empty-data handling missing"))),
        ("no_last_good_replay", lambda: "last_payload()" not in guard or (_ for _ in ()).throw(AssertionError("still replays stale payloads"))),
    ])
    return emit_report("E2-LS5-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
