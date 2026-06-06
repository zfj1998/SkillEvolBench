from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()


def run():
    baseline = read_text(PROJECT_ROOT / "quarterly_baseline.py")
    fingerprint = read_text(PROJECT_ROOT / "batch_fingerprint.py")
    script = read_text(PROJECT_ROOT / "build_quarterly_revenue_report.py")

    public = run_checks(
        "public",
        [
            ("has_baseline_module", lambda: "baseline_revenue" in baseline or (_ for _ in ()).throw(AssertionError("baseline helper missing"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("anomaly_threshold_is_not_too_permissive", lambda: "* 3" in baseline and "* 8" not in baseline or (_ for _ in ()).throw(AssertionError("anomaly threshold still too weak"))),
            ("duplicate_detection_uses_content_fingerprint", lambda: "sorted((str(row[\"date\"]), round(float(row[\"amount\"]), 2))" in fingerprint or (_ for _ in ()).throw(AssertionError("batch fingerprinting missing"))),
            ("script_applies_corrected_view", lambda: "dedupe_rows" in script and "corrected_quarterly_revenue" in script or (_ for _ in ()).throw(AssertionError("corrected view missing"))),
        ],
    )
    return emit_report("E3-LS5-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
