from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_amounts.py"
CSV_PATH = PROJECT / "sales_data.csv"
OUTPUT = PROJECT / "output.json"


def _expected(csv_path: Path):
    df = pd.read_csv(csv_path)
    total = round(float(pd.to_numeric(df[[column for column in df.columns if column.lower() == "amount"][0]], errors="raise").sum()), 2)
    return total


def _run(source: Path | None = None):
    if OUTPUT.exists():
        OUTPUT.unlink()
    env = os.environ.copy()
    if source is not None:
        env["SALES_SOURCE"] = str(source)
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60, env=env)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def _reordered_source() -> Path:
    df = pd.read_csv(CSV_PATH)
    temp_dir = Path(tempfile.mkdtemp(prefix="e3_ls1_t5_"))
    target = temp_dir / "sales_data_partner.csv"
    df = df[["Id", "Date", "Name", "Amount"]]
    df.to_csv(target, index=False)
    return target


def run():
    public_total = _expected(CSV_PATH)
    hidden_source = _reordered_source()
    hidden_total = _expected(hidden_source)
    public = run_checks("public", [
        ("total_exists", lambda: "total_amount" in _run()[1] or (_ for _ in ()).throw(AssertionError("total_amount missing"))),
        ("public_total_correct", lambda: abs(_run()[1].get("total_amount", 0.0) - public_total) < 0.01 or (_ for _ in ()).throw(AssertionError("public total mismatch"))),
    ])
    hidden = run_checks("hidden", [
        ("reordered_columns_supported", lambda: abs(_run(hidden_source)[1].get("total_amount", 0.0) - hidden_total) < 0.01 or (_ for _ in ()).throw(AssertionError("failed on reordered columns"))),
        ("metric_column_standardized", lambda: _run(hidden_source)[1].get("metric_column") == "amount" or (_ for _ in ()).throw(AssertionError("metric column not standardized"))),
        ("no_crash", lambda: _run(hidden_source)[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("script crashed on hidden source"))),
    ])
    return emit_report("E3-LS1-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
