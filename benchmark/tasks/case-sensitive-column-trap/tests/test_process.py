from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_amounts.py"
HELPER = PROJECT / "schema_casefold.py"


def run():
    script = read_text(SCRIPT)
    helper = read_text(HELPER)
    public = run_checks("public", [
        ("resolver_present", lambda: "resolve_metric_column" in helper or (_ for _ in ()).throw(AssertionError("column resolver missing"))),
    ])
    hidden = run_checks("hidden", [
        ("casefold_logic_present", lambda: ".lower()" in helper or ".casefold()" in helper or (_ for _ in ()).throw(AssertionError("case normalization missing"))),
        ("no_positional_fallback", lambda: "amount_index" not in helper and "[2]" not in helper or (_ for _ in ()).throw(AssertionError("positional shortcut detected"))),
    ])
    return emit_report("E3-LS1-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
