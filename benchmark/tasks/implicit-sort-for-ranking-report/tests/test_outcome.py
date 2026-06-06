from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_leaderboard.py"
CSV_PATH = PROJECT / "transactions.csv"
OUTPUT = PROJECT / "output.json"


def _expected():
    df = pd.read_csv(CSV_PATH)
    df["amount"] = pd.to_numeric(df["amount"], errors="raise")
    q3_df = df[df["date"].str.startswith(("2024-07", "2024-08", "2024-09"))].copy()
    totals = q3_df.groupby("salesperson", as_index=False)["amount"].sum().rename(columns={"amount": "total_sales"})
    cutoff = totals["total_sales"].nlargest(10).iloc[-1]
    ranked = totals[totals["total_sales"] >= cutoff].sort_values(["total_sales", "salesperson"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    return ranked


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    public = run_checks("public", [
        ("leaderboard_has_rows", lambda: _run()[1].get("row_count", 0) >= 10 or (_ for _ in ()).throw(AssertionError("leaderboard too short"))),
        ("records_present", lambda: len(_run()[1].get("records", [])) >= 10 or (_ for _ in ()).throw(AssertionError("records missing"))),
    ])
    hidden = run_checks("hidden", [
        ("top_rows_correct", lambda: _run()[1].get("records") == expected.to_dict(orient="records") or (_ for _ in ()).throw(AssertionError("leaderboard ranking mismatch"))),
        ("sorted_descending", lambda: [r["total_sales"] for r in _run()[1].get("records", [])] == sorted([r["total_sales"] for r in _run()[1].get("records", [])], reverse=True) or (_ for _ in ()).throw(AssertionError("leaderboard not sorted descending"))),
        ("top_total_correct", lambda: bool(_run()[1].get("records", [{}])[0].get("total_sales") == expected.iloc[0]["total_sales"]) or (_ for _ in ()).throw(AssertionError("top total incorrect"))),
        ("ties_included", lambda: len(_run()[1].get("records", [])) == len(expected) or (_ for _ in ()).throw(AssertionError("tie at cutoff not handled"))),
    ])
    return emit_report("E3-LS2-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
