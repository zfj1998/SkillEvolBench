from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_revenue.py"
CSV_PATH = PROJECT / "revenue.csv"
OUTPUT = PROJECT / "output.json"


def _expected():
    totals: dict[str, float] = {}
    names: set[str] = set()
    row_count = 0
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_count += 1
            amount = float(str(row["amount"]).replace("\u200b", "").replace(",", "").strip())
            totals[row["region"]] = totals.get(row["region"], 0.0) + amount
            names.add(row["name"])
    return {
        "row_count": row_count,
        "totals": {key: round(value, 2) for key, value in sorted(totals.items())},
        "names": names,
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
        ("output_exists", lambda: _run()[1] or (_ for _ in ()).throw(AssertionError("output.json missing"))),
        ("region_totals_present", lambda: isinstance(_run()[1].get("region_totals"), dict) or (_ for _ in ()).throw(AssertionError("region_totals missing"))),
    ])
    hidden = run_checks("hidden", [
        ("no_crash", lambda: _run()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("loader crashed"))),
        ("bom_removed", lambda: _run()[1].get("schema_report", {}).get("canonical_headers", [None])[0] == "region" or (_ for _ in ()).throw(AssertionError("BOM-prefixed header not normalized"))),
        ("unicode_names_preserved", lambda: any(any(ch in name for ch in "äöüÄÖÜß") for name in _run()[1].get("sample_names", [])) or (_ for _ in ()).throw(AssertionError("umlaut names not preserved"))),
        ("all_rows_retained", lambda: _run()[1].get("clean_row_count") == expected["row_count"] or (_ for _ in ()).throw(AssertionError("rows were dropped after normalization"))),
        ("totals_correct", lambda: _run()[1].get("region_totals") == expected["totals"] or (_ for _ in ()).throw(AssertionError("region totals mismatch"))),
    ])
    return emit_report("E3-LS1-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
