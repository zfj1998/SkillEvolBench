from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_logs.py"
PARSER = PROJECT / "date_parser.py"
POLICY = PROJECT / "ordering_policy.py"


def run():
    script = read_text(SCRIPT)
    parser = read_text(PARSER)
    policy = read_text(POLICY)
    public = run_checks("public", [
        ("date_parsing_present", lambda: "to_datetime" in parser or "strptime" in parser or (_ for _ in ()).throw(AssertionError("date parsing missing"))),
    ])
    hidden = run_checks("hidden", [
        ("sorts_by_parsed_date", lambda: "parsed_date" in policy or (_ for _ in ()).throw(AssertionError("sort does not use parsed dates"))),
        ("no_raw_date_sort", lambda: "[\"date\"" not in policy and "'date'" not in policy or (_ for _ in ()).throw(AssertionError("raw string date sort detected"))),
        ("stable_sort_kind", lambda: "mergesort" in policy or (_ for _ in ()).throw(AssertionError("stable sort kind missing"))),
    ])
    return emit_report("E3-LS2-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
