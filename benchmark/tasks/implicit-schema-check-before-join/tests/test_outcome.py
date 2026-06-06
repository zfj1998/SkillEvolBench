from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_orders.py"
USERS_PATH = PROJECT / "users.csv"
ORDERS_PATH = PROJECT / "orders.csv"
OUTPUT = PROJECT / "output.json"


def _expected():
    users = pd.read_csv(USERS_PATH)
    orders = pd.read_csv(ORDERS_PATH)
    users["user_id"] = users["user_id"].astype(int).map(lambda value: f"USR{value:03d}")
    orders["user_id"] = orders["user_id"].astype(str).str.strip().str.upper()
    merged = pd.merge(users, orders, on="user_id", how="inner")
    totals = merged.groupby("region")["amount"].sum().round(2).sort_index().to_dict()
    return {
        "row_count": int(len(merged)),
        "totals": {key: round(float(value), 2) for key, value in totals.items()},
        "regions": set(users["region"].unique()),
    }


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    public = run_checks("public", [
        ("result_non_empty", lambda: _run()[1].get("merged_row_count", 0) > 0 or (_ for _ in ()).throw(AssertionError("merge result empty"))),
    ])
    hidden = run_checks("hidden", [
        ("row_count_correct", lambda: _run()[1].get("merged_row_count") == expected["row_count"] or (_ for _ in ()).throw(AssertionError("merged row count mismatch"))),
        ("all_regions_present", lambda: set(_run()[1].get("region_totals", {}).keys()) == expected["regions"] or (_ for _ in ()).throw(AssertionError("missing regions in aggregation"))),
        ("totals_correct", lambda: _run()[1].get("region_totals") == expected["totals"] or (_ for _ in ()).throw(AssertionError("region totals mismatch"))),
        ("no_unmatched_orders", lambda: _run()[1].get("merge_report", {}).get("unmatched_orders") == 0 or (_ for _ in ()).throw(AssertionError("orders were left unmatched"))),
        ("dtype_report_present", lambda: all(key in _run()[1].get("merge_report", {}) for key in ["users_dtype_before", "orders_dtype_before", "users_dtype_after", "orders_dtype_after"]) or (_ for _ in ()).throw(AssertionError("dtype report missing"))),
    ])
    return emit_report("E3-LS1-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
