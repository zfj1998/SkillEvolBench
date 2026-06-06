from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
POLICY = PROJECT / "collation_policy.py"
SCRIPT = PROJECT / "process_contacts.py"


def run():
    policy = read_text(POLICY)
    script = read_text(SCRIPT)
    public = run_checks("public", [
        ("custom_collation_key_present", lambda: "german_sort_key" in policy or (_ for _ in ()).throw(AssertionError("collation key missing"))),
    ])
    hidden = run_checks("hidden", [
        ("umlaut_expansion_present", lambda: any(token in policy for token in ["ae", "oe", "ue", "ss"]) or (_ for _ in ()).throw(AssertionError("German transliteration missing"))),
        ("sorting_uses_collation_key", lambda: "_last_sort" in script and "_first_sort" in script or (_ for _ in ()).throw(AssertionError("collation key not used in sort"))),
    ])
    return emit_report("E3-LS2-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
