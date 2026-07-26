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
        [sys.executable, "build_march_sales_report.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def run():
    hidden = run_checks(
        "hidden",
        [
            ("calendar_guard_uses_valid_rows", lambda: _run_report()["days_with_data"] == 29 or (_ for _ in ()).throw(AssertionError("calendar completeness includes invalid rows"))),
            ("missing_days_derived_from_valid_rows", lambda: _run_report()["missing_days"] == ["2024-03-15", "2024-03-16"] or (_ for _ in ()).throw(AssertionError("missing days are not derived from valid rows"))),
            ("annotations_mark_any_gap_incomplete", lambda: _run_report()["completeness"] == "incomplete" and "2 days" in _run_report()["quality_note"] or (_ for _ in ()).throw(AssertionError("report does not mark the observed gaps incomplete"))),
        ],
    )
    return emit_report("E3-LS5-T4", {"section": "public", "results": [], "passed": 0, "total": 0}, hidden)


if __name__ == "__main__":
    print_report(run())
