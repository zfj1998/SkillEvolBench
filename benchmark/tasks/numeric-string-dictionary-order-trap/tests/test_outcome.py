from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_products.py"
CSV_PATH = PROJECT / "products.csv"
OUTPUT = PROJECT / "output.json"


def _expected():
    df = pd.read_csv(CSV_PATH, dtype={"product_id": str})
    df["_product_id_int"] = df["product_id"].map(lambda value: int(str(value).strip()))
    return df.sort_values(["_product_id_int", "name"], ascending=[True, True], kind="mergesort").reset_index(drop=True)


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
        ("natural_order_correct", lambda: [r["product_id"] for r in _run()[1].get("records", [])] == expected["product_id"].tolist() or (_ for _ in ()).throw(AssertionError("catalog not in natural numeric order"))),
        ("nine_before_ten", lambda: [r["product_id"] for r in _run()[1].get("records", [])].index("9") < [r["product_id"] for r in _run()[1].get("records", [])].index("10") or (_ for _ in ()).throw(AssertionError("9 does not appear before 10"))),
        ("legacy_zero_padded_ids_positioned_correctly", lambda: "007" in [r["product_id"] for r in _run()[1].get("records", [])] and [r["product_id"] for r in _run()[1].get("records", [])].index("007") < [r["product_id"] for r in _run()[1].get("records", [])].index("10") or (_ for _ in ()).throw(AssertionError("zero-padded ids not normalized correctly"))),
    ])
    return emit_report("E3-LS2-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
