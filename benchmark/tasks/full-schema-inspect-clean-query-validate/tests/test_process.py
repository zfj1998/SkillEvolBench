from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_pipeline.py"
INSPECTOR = PROJECT / "schema_inspector.py"
CLEANER = PROJECT / "amount_cleaner.py"
VALIDATOR = PROJECT / "totals_validator.py"
OUTPUT = PROJECT / "output.json"
EXPECTED = PROJECT / "expected_totals.json"


def _run_pipeline():
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
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    public = run_checks("public", [
        ("schema_inspection_present", lambda: set(_run_pipeline()["region_totals"]) == set(expected) or (_ for _ in ()).throw(AssertionError("canonical regions missing after schema inspection"))),
    ])
    hidden = run_checks("hidden", [
        ("amount_cleanup_handles_parentheses", lambda: all(abs(_run_pipeline()["region_totals"][region] - amount) <= max(amount * 0.01, 0.01) for region, amount in expected.items()) or (_ for _ in ()).throw(AssertionError("accounting-format amounts were not cleaned correctly"))),
        ("zwsp_cleanup_present", lambda: set(_run_pipeline()["region_totals"]) == set(expected) or (_ for _ in ()).throw(AssertionError("hidden characters prevented region normalization"))),
        ("validation_against_expected_present", lambda: {row["region"] for row in _run_pipeline()["validation_report"]} == set(expected) or (_ for _ in ()).throw(AssertionError("expected-total validation report incomplete"))),
        ("strict_threshold_present", lambda: all(row["passed"] for row in _run_pipeline()["validation_report"]) or (_ for _ in ()).throw(AssertionError("correct totals did not pass the documented 1% threshold"))),
        ("header_normalization_present", lambda: set(_run_pipeline()["region_totals"]) == set(expected) or (_ for _ in ()).throw(AssertionError("header normalization failed"))),
    ])
    return emit_report("E3-LS1-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
