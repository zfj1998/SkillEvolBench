from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_transactions.py"
PARSER = PROJECT / "amount_parser.py"


def run():
    script = read_text(SCRIPT)
    parser = read_text(PARSER)
    public = run_checks("public", [
        ("parser_exists", lambda: "parse_revenue" in parser or (_ for _ in ()).throw(AssertionError("parse_revenue missing"))),
    ])
    hidden = run_checks("hidden", [
        ("currency_cleanup_present", lambda: "$" in parser or (_ for _ in ()).throw(AssertionError("currency cleanup missing"))),
        ("comma_cleanup_present", lambda: ".replace(\",\", \"\")" in parser or (_ for _ in ()).throw(AssertionError("comma cleanup missing"))),
        ("accounting_negative_logic", lambda: "startswith(\"(\")" in parser or "negative =" in parser or (_ for _ in ()).throw(AssertionError("accounting negative handling missing"))),
        ("nan_audit_present", lambda: "anomaly_report" in script or (_ for _ in ()).throw(AssertionError("anomaly audit missing"))),
    ])
    return emit_report("E3-LS1-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
