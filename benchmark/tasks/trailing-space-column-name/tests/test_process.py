from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_sales.py"
REGISTRY = PROJECT / "schema_registry.py"


def run():
    script = read_text(SCRIPT)
    registry = read_text(REGISTRY)
    public = run_checks("public", [
        ("normalizes_headers", lambda: ".strip()" in registry or (_ for _ in ()).throw(AssertionError("header strip missing"))),
    ])
    hidden = run_checks("hidden", [
        ("checks_schema_before_aggregation", lambda: "require_canonical_columns" in script or (_ for _ in ()).throw(AssertionError("schema check missing"))),
        ("does_not_use_positional_columns", lambda: "iloc" not in script or (_ for _ in ()).throw(AssertionError("positional column access detected"))),
        ("id_cast_present", lambda: "pd.to_numeric(df[\"id\"]" in script or "astype(int)" in script or (_ for _ in ()).throw(AssertionError("id normalization missing"))),
    ])
    return emit_report("E3-LS1-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
