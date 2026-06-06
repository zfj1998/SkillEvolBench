from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()


def run():
    anomaly = read_text(PROJECT_ROOT / "revenue_anomaly.py")
    consistency = read_text(PROJECT_ROOT / "consistency_guard.py")
    office = read_text(PROJECT_ROOT / "office_registry.py")
    confidence = read_text(PROJECT_ROOT / "confidence_policy.py")

    hidden = run_checks(
        "hidden",
        [
            ("revenue_anomaly_groups_by_region_month", lambda: "grouped[(str(row[\"month\"]), str(row[\"region\"]))]" in anomaly or (_ for _ in ()).throw(AssertionError("region-month grouping missing"))),
            ("revenue_anomaly_flags_duplicate_batches", lambda: "duplicate_region_month_batches" in anomaly and "duplicate_batches" in anomaly or (_ for _ in ()).throw(AssertionError("duplicate batch issue missing"))),
            ("consistency_guard_uses_cent_level_tolerance", lambda: "<= 0.01" in consistency and "0.1" not in consistency or (_ for _ in ()).throw(AssertionError("allocation tolerance too loose"))),
            ("office_registry_validates_status_values", lambda: "VALID_STATUSES" in office and "invalid_status_rows" in office or (_ for _ in ()).throw(AssertionError("office status validation missing"))),
            ("confidence_policy_supports_low_confidence", lambda: '"low"' in confidence and "issue_count == 1" in confidence or (_ for _ in ()).throw(AssertionError("confidence policy too weak"))),
        ],
    )
    return emit_report("E3-LS5-T6", {"section": "public", "results": [], "passed": 0, "total": 0}, hidden)


if __name__ == "__main__":
    print_report(run())
