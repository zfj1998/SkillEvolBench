from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "merge_supplier_inventory.py"
OUTPUT = PROJECT / "output.json"


def _standardize_value(source: str, column: str, value: object):
    if value is None:
        return np.nan
    text = str(value).strip()
    lower = text.lower()
    if source == "supplier_a":
        return np.nan if text == "" else text
    if source == "supplier_b":
        return np.nan if lower in {"", "na", "n/a", "null", "none"} else text
    if source == "supplier_c":
        if column == "price":
            return np.nan if lower in {"-1", "-1.0", "-999", "-999.0", "0", "0.0"} else text
        if column == "stock":
            return np.nan if lower in {"-1", "-1.0", "-999", "-999.0"} else text
    return np.nan if lower in {"", "na", "n/a", "null", "none"} else text


def _expected() -> dict:
    frames: list[pd.DataFrame] = []
    for source in ("supplier_a", "supplier_b", "supplier_c"):
        frame = pd.read_csv(PROJECT / f"{source}.csv", keep_default_na=False)
        frame["source"] = source
        for column in ("price", "stock"):
            frame[column] = frame[column].map(lambda value, s=source, c=column: _standardize_value(s, c, value))
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    valid_price = combined["price"].dropna()
    category_totals: dict[str, dict[str, float | int | None]] = {}
    for category, group in combined.groupby("category", dropna=False):
        prices = group["price"].dropna()
        category_totals[str(category)] = {
            "valid_price_count": int(prices.shape[0]),
            "average_price": round(float(prices.mean()), 2) if not prices.empty else None,
            "total_stock": int(group["stock"].dropna().sum()),
        }
    source_summary: dict[str, dict[str, int]] = {}
    for source, group in combined.groupby("source", dropna=False):
        source_summary[str(source)] = {
            "missing_price": int(group["price"].isna().sum()),
            "missing_stock": int(group["stock"].isna().sum()),
            "out_of_stock_count": int((group["stock"] == 0).sum()),
        }
    return {
        "record_count": int(combined.shape[0]),
        "valid_price_count": int(valid_price.shape[0]),
        "missing_price_count": int(combined["price"].isna().sum()),
        "average_price": round(float(valid_price.mean()), 2),
        "total_stock": int(combined["stock"].dropna().sum()),
        "out_of_stock_count": int((combined["stock"] == 0).sum()),
        "source_null_summary": source_summary,
        "category_totals": category_totals,
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
        ("output_exists", lambda: (_run(), OUTPUT.exists())[1] or (_ for _ in ()).throw(AssertionError("output.json missing"))),
        ("record_count_present", lambda: _run()[1].get("record_count", 0) >= 1 or (_ for _ in ()).throw(AssertionError("record_count missing"))),
    ])
    hidden = run_checks("hidden", [
        ("script_does_not_crash", lambda: _run()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError(_run()[0].stderr[:400]))),
        ("summary_matches_ground_truth", lambda: _run()[1].get("record_count") == expected["record_count"] and _run()[1].get("valid_price_count") == expected["valid_price_count"] and _run()[1].get("missing_price_count") == expected["missing_price_count"] and _run()[1].get("total_stock") == expected["total_stock"] and _run()[1].get("out_of_stock_count") == expected["out_of_stock_count"] or (_ for _ in ()).throw(AssertionError("top-level summary mismatch"))),
        ("source_null_summary_matches", lambda: _run()[1].get("source_null_summary") == expected["source_null_summary"] or (_ for _ in ()).throw(AssertionError("per-source null summary mismatch"))),
        ("category_totals_match", lambda: _run()[1].get("category_totals") == expected["category_totals"] or (_ for _ in ()).throw(AssertionError("category totals mismatch"))),
    ])
    return emit_report("E3-LS4-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
