from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
REGISTRY = PROJECT / "sentinel_registry.py"
SCRIPT = PROJECT / "summarize_employee_metrics.py"


def run():
    registry = read_text(REGISTRY)
    script = read_text(SCRIPT)
    public = run_checks("public", [
        ("uses_column_specific_cleaners", lambda: "clean_age" in registry and "clean_salary" in registry and "clean_temperature" in registry or (_ for _ in ()).throw(AssertionError("column-specific cleaners missing"))),
    ])
    hidden = run_checks("hidden", [
        ("age_has_minus_one_sentinel", lambda: "AGE_MISSING" in registry and "-1" in registry or (_ for _ in ()).throw(AssertionError("age sentinel handling missing"))),
        ("salary_does_not_treat_zero_missing", lambda: "0" not in registry.split("SALARY_MISSING", 1)[-1].split("}", 1)[0] or (_ for _ in ()).throw(AssertionError("salary=0 still treated as missing"))),
        ("temperature_has_sensor_fault_sentinel", lambda: "sensor_fault" in registry and "-999" in registry or (_ for _ in ()).throw(AssertionError("temperature sentinel handling missing"))),
        ("reads_dictionary_driven_columns", lambda: "site_temperature" in script and "salary_zero_count" in script or (_ for _ in ()).throw(AssertionError("metric summary missing data-dictionary semantics"))),
    ])
    return emit_report("E3-LS4-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
