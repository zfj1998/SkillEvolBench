from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_pipeline.py"
EXPECTED_PATH = PROJECT / "expected_totals.json"
OUTPUT = PROJECT / "output.json"


def _expected():
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    public = run_checks("public", [
        ("output_exists", lambda: _run()[1] or (_ for _ in ()).throw(AssertionError("output missing"))),
        ("validation_report_present", lambda: isinstance(_run()[1].get("validation_report"), list) or (_ for _ in ()).throw(AssertionError("validation report missing"))),
    ])
    hidden = run_checks("hidden", [
        ("per_region_totals_correct", lambda: all(abs(_run()[1].get("region_totals", {}).get(region, 0.0) - expected[region]) <= max(expected[region] * 0.01, 0.01) for region in expected) or (_ for _ in ()).throw(AssertionError("region totals outside 1% tolerance"))),
        ("all_regions_present", lambda: set(_run()[1].get("region_totals", {}).keys()) == set(expected.keys()) or (_ for _ in ()).throw(AssertionError("missing region totals"))),
        ("validation_lists_each_region", lambda: {item["region"] for item in _run()[1].get("validation_report", [])} == set(expected.keys()) or (_ for _ in ()).throw(AssertionError("validation report incomplete"))),
        ("validation_matches_actual_deltas", lambda: (_run()[1].get("validation_report") and all((abs(_run()[1]["region_totals"][item["region"]] - expected[item["region"]]) <= max(expected[item["region"]] * 0.01, 0.01)) == bool(item["passed"]) for item in _run()[1].get("validation_report", []))) or (_ for _ in ()).throw(AssertionError("validation pass/fail flags do not match actual totals"))),
        ("no_crash", lambda: _run()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("pipeline crashed"))),
    ])
    return emit_report("E3-LS1-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
