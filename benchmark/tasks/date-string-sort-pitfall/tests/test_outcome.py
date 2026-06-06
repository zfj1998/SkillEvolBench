from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_logs.py"
CSV_PATH = PROJECT / "server_logs.csv"
OUTPUT = PROJECT / "output.json"


def _expected():
    df = pd.read_csv(CSV_PATH)
    df["parsed_date"] = pd.to_datetime(df["date"], errors="coerce")
    sorted_df = df.sort_values(["parsed_date", "time", "log_id"], kind="mergesort").reset_index(drop=True)
    return sorted_df


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    public = run_checks("public", [
        ("row_count_preserved", lambda: _run()[1].get("row_count") == len(expected) or (_ for _ in ()).throw(AssertionError("row count mismatch"))),
        ("date_range_present", lambda: _run()[1].get("first_date") and _run()[1].get("last_date") or (_ for _ in ()).throw(AssertionError("date range missing"))),
    ])
    hidden = run_checks("hidden", [
        ("strict_time_order", lambda: [record["log_id"] for record in _run()[1].get("records", [])] == expected["log_id"].tolist() or (_ for _ in ()).throw(AssertionError("logs not in chronological order"))),
        ("non_lexicographic_pair_fixed", lambda: bool(expected.loc[expected["date"] == "12/1/2024"].index.min() < expected.loc[expected["date"] == "1/9/2024"].index.max()) if {"12/1/2024", "1/9/2024"}.issubset(set(expected["date"])) else True),
        ("mixed_formats_preserved", lambda: len(_run()[1].get("records", [])) == 1000 or (_ for _ in ()).throw(AssertionError("records missing after parsing"))),
        ("no_crash", lambda: _run()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("script crashed"))),
    ])
    return emit_report("E3-LS2-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
