from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_transactions.py"
CSV_PATH = PROJECT / "transactions.csv"
OUTPUT = PROJECT / "output.json"


def _parse_expected(raw: str) -> float | None:
    text = str(raw).strip()
    if text.lower() in {"", "n/a", "null", "-"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace("$", "").replace(",", "")
    value = float(text)
    return -value if negative else value


def _expected():
    category_totals: dict[str, float] = {}
    total = 0.0
    valid_rows = 0
    null_like = 0
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            value = _parse_expected(row["revenue"])
            if value is None:
                null_like += 1
                continue
            valid_rows += 1
            total += value
            category_totals[row["category"]] = category_totals.get(row["category"], 0.0) + value
    return {
        "total_revenue": round(total, 2),
        "valid_rows": valid_rows,
        "category_totals": {key: round(value, 2) for key, value in sorted(category_totals.items())},
        "null_like": null_like,
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
        ("output_exists", lambda: _run()[1] or (_ for _ in ()).throw(AssertionError("output missing"))),
        ("total_present", lambda: "total_revenue" in _run()[1] or (_ for _ in ()).throw(AssertionError("total_revenue missing"))),
    ])
    hidden = run_checks("hidden", [
        ("comma_values_included", lambda: _run()[1].get("total_revenue") >= expected["total_revenue"] - 0.01 or (_ for _ in ()).throw(AssertionError("comma-formatted values not included"))),
        ("category_totals_correct", lambda: _run()[1].get("category_totals") == expected["category_totals"] or (_ for _ in ()).throw(AssertionError("category totals mismatch"))),
        ("accounting_negatives_handled", lambda: abs(_run()[1].get("total_revenue", 0.0) - expected["total_revenue"]) < 0.01 or (_ for _ in ()).throw(AssertionError("accounting negatives not handled"))),
        ("null_rows_do_not_crash", lambda: _run()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("job crashed"))),
        ("valid_row_count_correct", lambda: _run()[1].get("valid_row_count") == expected["valid_rows"] or (_ for _ in ()).throw(AssertionError("valid row count mismatch"))),
        ("anomaly_report_correct", lambda: _run()[1].get("anomaly_report", {}).get("null_like_rows") == expected["null_like"] and "parse_failures" in _run()[1].get("anomaly_report", {}) or (_ for _ in ()).throw(AssertionError("anomaly report mismatch"))),
    ])
    return emit_report("E3-LS1-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
