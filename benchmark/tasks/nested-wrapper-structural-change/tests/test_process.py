from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"


def run():
    router = read_text(PROJECT / "schema_router.py")
    policy = read_text(PROJECT / "rollout_policy.py")
    public = run_checks("public", [
        ("supports_nested_wrapper", lambda: ("result" in router and "items" in router) or (_ for _ in ()).throw(AssertionError("nested result.items path missing"))),
    ])
    hidden = run_checks("hidden", [
        ("supports_legacy_data", lambda: "\"data\"" in router or (_ for _ in ()).throw(AssertionError("legacy data path missing"))),
        ("does_not_prefer_transitional_top_level", lambda: "data_contract" not in policy or "return False" in policy or (_ for _ in ()).throw(AssertionError("still prefers transitional top-level data"))),
        ("dual_path_extraction_present", lambda: ("return result[\"items\"]" in router or "result.get(\"items\")" in router) and "payload.get(\"data\")" in router or (_ for _ in ()).throw(AssertionError("expected both extraction paths"))),
    ])
    return emit_report("E2-LS5-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
