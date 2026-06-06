from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_leaderboard.py"
POLICY = PROJECT / "leaderboard_policy.py"


def run():
    script = read_text(SCRIPT)
    policy = read_text(POLICY)
    public = run_checks("public", [
        ("groupby_present", lambda: "groupby" in policy or (_ for _ in ()).throw(AssertionError("groupby missing"))),
    ])
    hidden = run_checks("hidden", [
        ("ranking_sort_present", lambda: "sort_values" in policy or "nlargest" in policy or (_ for _ in ()).throw(AssertionError("ranking sort missing"))),
        ("tie_cutoff_logic_present", lambda: "cutoff" in policy or ">= cutoff" in policy or (_ for _ in ()).throw(AssertionError("tie cutoff handling missing"))),
        ("q3_filter_used", lambda: "q3_only" in script or (_ for _ in ()).throw(AssertionError("Q3 filtering missing"))),
    ])
    return emit_report("E3-LS2-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
