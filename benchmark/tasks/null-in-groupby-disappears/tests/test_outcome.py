from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "aggregate_regional_sales.py"
INPUT = PROJECT / "regional_sales.csv"
OUTPUT = PROJECT / "output.json"
sys.path.insert(0, str(PROJECT))

from region_normalizer import UNKNOWN_REGION, normalize_region


def _expected() -> dict:
    frame = pd.read_csv(INPUT)
    frame["amount"] = pd.to_numeric(frame["amount"].astype(str).str.replace(",", "", regex=False), errors="coerce")
    frame["normalized_region"] = frame["region"].map(normalize_region).fillna(UNKNOWN_REGION)
    grouped = (
        frame.groupby("normalized_region", as_index=False)["amount"]
        .sum()
        .rename(columns={"normalized_region": "region", "amount": "total_amount"})
        .sort_values("region", kind="mergesort")
        .reset_index(drop=True)
    )
    return {
        "records": grouped.to_dict(orient="records"),
        "source_total": round(float(frame["amount"].sum()), 2),
        "unresolved_row_count": int((frame["normalized_region"] == UNKNOWN_REGION).sum()),
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
        ("at_least_four_regions", lambda: len(_run()[1].get("records", [])) >= 4 or (_ for _ in ()).throw(AssertionError("too few groups returned"))),
    ])
    hidden = run_checks("hidden", [
        ("keeps_unknown_group", lambda: any(record.get("region") == UNKNOWN_REGION for record in _run()[1].get("records", [])) or (_ for _ in ()).throw(AssertionError("unknown region group disappeared"))),
        ("has_five_groups", lambda: len(_run()[1].get("records", [])) == 5 or (_ for _ in ()).throw(AssertionError("expected 5 canonical region groups"))),
        ("grouped_total_matches_source", lambda: round(_run()[1].get("grouped_total", 0.0), 2) == expected["source_total"] or (_ for _ in ()).throw(AssertionError("grouped total does not match source total"))),
        ("unknown_row_count_matches", lambda: _run()[1].get("unresolved_row_count") == expected["unresolved_row_count"] or (_ for _ in ()).throw(AssertionError("unresolved row count incorrect"))),
        ("records_match_expected", lambda: _run()[1].get("records") == expected["records"] or (_ for _ in ()).throw(AssertionError("regional totals incorrect"))),
    ])
    return emit_report("E3-LS4-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
