from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "compute_order_metrics.py"
ORDERS = PROJECT / "orders.csv"
OUTPUT = PROJECT / "output.json"


def _expected() -> dict:
    frame = pd.read_csv(ORDERS)
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    valid = frame["amount"].dropna()
    return {
        "average_amount": round(float(valid.mean()), 4),
        "missing_amount_count": int(frame["amount"].isna().sum()),
        "valid_amount_count": int(valid.shape[0]),
        "denominator_used": int(valid.shape[0]),
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
        ("average_present", lambda: "average_amount" in _run()[1] or (_ for _ in ()).throw(AssertionError("average_amount missing"))),
        ("output_created", lambda: OUTPUT.exists() or (_ for _ in ()).throw(AssertionError("output.json missing"))),
    ])
    hidden = run_checks("hidden", [
        ("average_matches_ground_truth", lambda: abs(_run()[1].get("average_amount", 0.0) - expected["average_amount"]) <= 0.01 or (_ for _ in ()).throw(AssertionError("average uses the wrong denominator"))),
        ("missing_amounts_reported", lambda: _run()[1].get("missing_amount_count") == expected["missing_amount_count"] or (_ for _ in ()).throw(AssertionError("missing amount count incorrect"))),
        ("valid_count_matches", lambda: _run()[1].get("valid_amount_count") == expected["valid_amount_count"] or (_ for _ in ()).throw(AssertionError("valid amount count incorrect"))),
        ("denominator_policy_is_correct", lambda: _run()[1].get("denominator_used") == expected["denominator_used"] and _run()[1].get("denominator_strategy") == "valid_amount_rows" or (_ for _ in ()).throw(AssertionError("denominator policy is not explicit or incorrect"))),
        ("count_consistency_flag", lambda: _run()[1].get("sanity_checks", {}).get("count_consistent") is True or (_ for _ in ()).throw(AssertionError("count consistency sanity check failed"))),
        ("denominator_sanity_flag", lambda: _run()[1].get("sanity_checks", {}).get("denominator_matches_valid_rows") is True or (_ for _ in ()).throw(AssertionError("denominator sanity check failed"))),
        ("average_band_flag", lambda: _run()[1].get("sanity_checks", {}).get("average_in_expected_band") is True or (_ for _ in ()).throw(AssertionError("average sanity band failed"))),
    ])
    return emit_report("E3-LS4-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
