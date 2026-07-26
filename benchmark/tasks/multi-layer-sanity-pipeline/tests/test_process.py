from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()
OUTPUT = PROJECT_ROOT / "output.json"


def _run_report():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run(
        [sys.executable, "build_operations_quality_report.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def _issue_kinds():
    return {row["kind"] for row in _run_report()["issues"]}


def run():
    hidden = run_checks(
        "hidden",
        [
            ("revenue_anomaly_groups_by_region_month", lambda: "revenue_spike" in _issue_kinds() or (_ for _ in ()).throw(AssertionError("region-month anomaly missing"))),
            ("revenue_anomaly_flags_duplicate_batches", lambda: "duplicate_region_month_batches" in _issue_kinds() or (_ for _ in ()).throw(AssertionError("duplicate batch issue missing"))),
            ("consistency_guard_uses_cent_level_tolerance", lambda: _run_report()["cross_query"]["match"] is False or (_ for _ in ()).throw(AssertionError("allocation mismatch was hidden by loose tolerance"))),
            ("office_registry_validates_status_values", lambda: len(_run_report()["office_registry"]["invalid_status_rows"]) == 1 or (_ for _ in ()).throw(AssertionError("office status validation missing"))),
            ("confidence_policy_supports_low_confidence", lambda: _run_report()["confidence"] == "low" or (_ for _ in ()).throw(AssertionError("multiple issues should lower confidence"))),
        ],
    )
    return emit_report("E3-LS5-T6", {"section": "public", "results": [], "passed": 0, "total": 0}, hidden)


if __name__ == "__main__":
    print_report(run())
