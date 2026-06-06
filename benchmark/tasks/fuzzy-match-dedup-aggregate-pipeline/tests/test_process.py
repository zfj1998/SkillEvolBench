from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
NORMALIZER = PROJECT / "company_normalizer.py"
SCRIPT = PROJECT / "process_customer_totals.py"
DEDUP = PROJECT / "dedup_policy.py"


def run():
    normalizer = read_text(NORMALIZER)
    script = read_text(SCRIPT)
    dedup = read_text(DEDUP)
    public = run_checks("public", [
        ("has_company_normalization", lambda: "canonical_company" in normalizer or (_ for _ in ()).throw(AssertionError("company normalization missing"))),
    ])
    hidden = run_checks("hidden", [
        ("has_alias_mapping", lambda: "COMPANY_ALIASES" in normalizer or (_ for _ in ()).throw(AssertionError("alias mapping missing"))),
        ("no_city_fallback_merge", lambda: "city_fallback" not in script or (_ for _ in ()).throw(AssertionError("city fallback fanout still present"))),
        ("dedup_policies_present", lambda: "drop_duplicates" in dedup or (_ for _ in ()).throw(AssertionError("dedup policy missing"))),
    ])
    return emit_report("E3-LS3-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
