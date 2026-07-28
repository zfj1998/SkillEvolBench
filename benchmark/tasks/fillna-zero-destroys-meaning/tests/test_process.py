from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
POLICY = PROJECT / "offline_policy.py"
SCRIPT = PROJECT / "compute_temperature_summary.py"
CLASSIFIER = PROJECT / "reading_classifier.py"
OUTPUT = PROJECT / "output.json"


def _run_summary():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def run():
    public = run_checks("public", [
        ("parses_numeric_temperatures", lambda: isinstance(_run_summary()["average_temperature"], (int, float)) or (_ for _ in ()).throw(AssertionError("temperature parsing missing"))),
    ])
    hidden = run_checks("hidden", [
        ("does_not_fill_missing_with_zero", lambda: _run_summary()["offline_reading_count"] > 0 or (_ for _ in ()).throw(AssertionError("offline readings were converted to zero"))),
        ("uses_dropna_or_mean", lambda: _run_summary()["valid_reading_count"] + _run_summary()["offline_reading_count"] > 0 or (_ for _ in ()).throw(AssertionError("valid-reading average strategy missing"))),
        ("does_not_reclassify_zero_as_offline", lambda: _run_summary()["zero_degree_count"] > 0 and _run_summary()["offline_reading_count"] > 0 or (_ for _ in ()).throw(AssertionError("zero-degree and offline readings are not distinguished"))),
        ("reports_offline_counts", lambda: {"offline_reading_count", "zero_degree_count", "valid_reading_count"} <= set(_run_summary()) or (_ for _ in ()).throw(AssertionError("offline/zero audit missing"))),
    ])
    return emit_report("E3-LS4-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
