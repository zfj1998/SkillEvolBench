from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_employees.py"
CSV_PATH = PROJECT / "employees.csv"
OUTPUT = PROJECT / "output.json"


def _expected():
    df = pd.read_csv(CSV_PATH)
    df["_feed_order"] = range(len(df))
    return df.sort_values(["department", "salary", "_feed_order"], ascending=[True, False, True], kind="mergesort").reset_index(drop=True)


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    public = run_checks("public", [
        ("row_count_correct", lambda: _run()[1].get("row_count") == len(expected) or (_ for _ in ()).throw(AssertionError("row count mismatch"))),
        ("records_present", lambda: len(_run()[1].get("records", [])) == len(expected) or (_ for _ in ()).throw(AssertionError("records missing"))),
    ])
    hidden = run_checks("hidden", [
        ("stable_order_preserved", lambda: [r["employee_id"] for r in _run()[1].get("records", [])] == expected["employee_id"].tolist() or (_ for _ in ()).throw(AssertionError("stable order requirement not met"))),
        ("department_order_correct", lambda: expected["department"].tolist() == [r["department"] for r in _run()[1].get("records", [])] or (_ for _ in ()).throw(AssertionError("department ordering wrong"))),
        ("no_row_loss", lambda: _run()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("script crashed"))),
    ])
    return emit_report("E3-LS2-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
