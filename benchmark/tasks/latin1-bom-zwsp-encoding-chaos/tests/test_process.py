from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_revenue.py"
CONTRACT = PROJECT / "encoding_contract.py"
CLEANER = PROJECT / "revenue_cleaner.py"


def run():
    script = read_text(SCRIPT)
    contract = read_text(CONTRACT)
    cleaner = read_text(CLEANER)
    public = run_checks("public", [
        ("encoding_declared", lambda: "encoding=" in script or (_ for _ in ()).throw(AssertionError("file encoding not declared"))),
    ])
    hidden = run_checks("hidden", [
        ("bom_cleanup_present", lambda: "\\ufeff" in contract or ".replace(" in contract or (_ for _ in ()).throw(AssertionError("BOM cleanup missing"))),
        ("zwsp_cleanup_present", lambda: "\\u200b" in cleaner or (_ for _ in ()).throw(AssertionError("ZWSP cleanup missing"))),
        ("schema_checked_before_parsing", lambda: "resolve_headers" in script or (_ for _ in ()).throw(AssertionError("schema contract missing"))),
    ])
    return emit_report("E3-LS1-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
