from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_sales.py"
CSV_PATH = PROJECT / "sales.csv"
OUTPUT = PROJECT / "output.json"


def _expected():
    with CSV_PATH.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        reader.fieldnames = [field.strip() for field in reader.fieldnames or []]
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for row in reader:
            totals[row["name"]] = totals.get(row["name"], 0.0) + float(row["amount"])
            counts[row["name"]] = counts.get(row["name"], 0) + 1
    return {
        "row_count": sum(counts.values()),
        "grand_total": round(sum(totals.values()), 2),
        "names": set(totals.keys()),
        "summary": {
            name: {
                "total_amount": round(totals[name], 2),
                "average_amount": round(totals[name] / counts[name], 2),
                "transaction_count": counts[name],
            }
            for name in totals
        },
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
        ("output_exists", lambda: (_run()[0].returncode == 0 and OUTPUT.exists()) or (_ for _ in ()).throw(AssertionError("output.json missing"))),
        ("summary_present", lambda: isinstance(_run()[1].get("summary"), list) or (_ for _ in ()).throw(AssertionError("summary missing"))),
    ])
    hidden = run_checks("hidden", [
        ("no_crash", lambda: _run()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("script crashed"))),
        ("grand_total_correct", lambda: abs(_run()[1]["grand_total"] - expected["grand_total"]) < 0.01 or (_ for _ in ()).throw(AssertionError("grand total mismatch"))),
        ("row_count_correct", lambda: _run()[1]["row_count"] == expected["row_count"] or (_ for _ in ()).throw(AssertionError("row count mismatch"))),
        ("all_names_present", lambda: {item["name"] for item in _run()[1]["summary"]} == expected["names"] or (_ for _ in ()).throw(AssertionError("summary missing names"))),
        ("per_name_aggregates_correct", lambda: _check_per_name_aggregates(_run()[1], expected) or True),
        ("id_schema_repaired", lambda: _run()[1].get("schema_report", {}).get("id_dtype") in {"int64", "int32", "int"} or (_ for _ in ()).throw(AssertionError("id dtype not repaired"))),
    ])
    return emit_report("E3-LS1-T1", public, hidden)


def _check_per_name_aggregates(payload, expected):
    rows = {item["name"]: item for item in payload["summary"]}
    for name, metrics in expected["summary"].items():
        row = rows.get(name)
        if row is None:
            raise AssertionError(f"missing summary row for {name}")
        if abs(float(row.get("total_amount", -1)) - metrics["total_amount"]) >= 0.01:
            raise AssertionError(f"{name} total_amount mismatch")
        if abs(float(row.get("average_amount", -1)) - metrics["average_amount"]) >= 0.01:
            raise AssertionError(f"{name} average_amount mismatch")
        if int(row.get("transaction_count", -1)) != metrics["transaction_count"]:
            raise AssertionError(f"{name} transaction_count mismatch")
    return True


if __name__ == "__main__":
    print_report(run())
