from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "compute_temperature_summary.py"
DATA = PROJECT / "temperature_readings.csv"
OUTPUT = PROJECT / "output.json"


def _expected() -> dict:
    frame = pd.read_csv(DATA)
    temperatures = pd.to_numeric(frame["temperature"], errors="coerce")
    valid = temperatures.dropna()
    return {
        "average_temperature": round(float(valid.mean()), 4),
        "offline_reading_count": int(temperatures.isna().sum()),
        "zero_degree_count": int((valid == 0).sum()),
        "valid_reading_count": int(valid.shape[0]),
    }


def _run() -> tuple[subprocess.CompletedProcess[str], dict]:
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    public = run_checks("public", [
        ("average_in_reasonable_range", lambda: -20.0 < _run()[1].get("average_temperature", 0.0) < 45.0 or (_ for _ in ()).throw(AssertionError("average outside plausible range"))),
    ])
    hidden = run_checks("hidden", [
        ("average_matches_ground_truth", lambda: abs(_run()[1].get("average_temperature", 0.0) - expected["average_temperature"]) <= 0.01 or (_ for _ in ()).throw(AssertionError("offline rows were incorrectly turned into zeros"))),
        ("zero_degree_rows_preserved", lambda: _run()[1].get("zero_degree_count") == expected["zero_degree_count"] or (_ for _ in ()).throw(AssertionError("real zero-degree readings were not preserved"))),
        ("offline_rows_excluded_from_average", lambda: _run()[1].get("valid_reading_count") == expected["valid_reading_count"] or (_ for _ in ()).throw(AssertionError("valid reading count incorrect"))),
        ("offline_rows_reported", lambda: _run()[1].get("offline_reading_count") == expected["offline_reading_count"] or (_ for _ in ()).throw(AssertionError("offline reading count incorrect"))),
    ])
    return emit_report("E3-LS4-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
