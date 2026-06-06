from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "compare_sales.py"
SALES_2023 = PROJECT / "sales_2023.csv"
SALES_2024 = PROJECT / "sales_2024.csv"
OUTPUT = PROJECT / "output.json"


def _canonical(value: str) -> str:
    normalized = str(value).replace("\u200b", "").strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    alias_map = {
        "ultra hd smart television 55 inch": "ultra hd smart television 55-inch",
        "ultra hd smart television 55-inch": "ultra hd smart television 55-inch",
        "wireless bluetooth noise cancelling headphones": "wireless bluetooth noise cancelling headphones",
        "wireless bluetooth noise-cancelling headphones": "wireless bluetooth noise cancelling headphones",
    }
    return alias_map.get(normalized, normalized)


def _prepare(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["canonical_product"] = df["product_name"].map(_canonical)
    df["revenue"] = pd.to_numeric(
        df["revenue"]
        .astype(str)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )
    df = df.sort_values(["canonical_product", "snapshot_id"], kind="mergesort").drop_duplicates(subset=["canonical_product"], keep="last")
    return df


def _expected():
    sales_2023 = _prepare(SALES_2023)
    sales_2024 = _prepare(SALES_2024)
    merged = sales_2023.merge(sales_2024[["canonical_product", "revenue"]], on="canonical_product", how="outer", suffixes=("_2023", "_2024"))
    merged["growth_rate"] = ((merged["revenue_2024"] - merged["revenue_2023"]) / merged["revenue_2023"]).round(4)
    merged["trend"] = merged["growth_rate"].map(lambda value: "growth" if pd.notna(value) and value > 0.2 else ("decline" if pd.notna(value) and value < -0.1 else "flat"))
    return merged


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    coverage = float((expected["revenue_2023"].notna() & expected["revenue_2024"].notna()).sum() / expected["revenue_2023"].notna().sum())

    def _actual_records() -> pd.DataFrame:
        return pd.DataFrame(_run()[1].get("records", []))

    def _records_match_expected() -> bool:
        actual = _actual_records().reindex(columns=list(expected.columns))
        return actual.fillna("__NA__").astype(str).equals(expected.fillna("__NA__").astype(str))

    def _matched_product(name: str) -> bool:
        actual = _actual_records()
        if "canonical_product" not in actual.columns:
            return False
        rows = actual[actual["canonical_product"] == name]
        if rows.empty:
            return False
        row = rows.iloc[0]
        return pd.notna(row.get("revenue_2023")) and pd.notna(row.get("revenue_2024"))

    public = run_checks("public", [
        ("records_present", lambda: len(_run()[1].get("records", [])) > 0 or (_ for _ in ()).throw(AssertionError("comparison output missing"))),
    ])
    hidden = run_checks("hidden", [
        ("coverage_above_90pct", lambda: _run()[1].get("coverage_ratio", 0) >= 0.9 or (_ for _ in ()).throw(AssertionError("coverage below 90%"))),
        ("tv_alias_matched", lambda: _matched_product("ultra hd smart television 55-inch") or (_ for _ in ()).throw(AssertionError("tv alias not aligned"))),
        ("headphones_alias_matched", lambda: _matched_product("wireless bluetooth noise cancelling headphones") or (_ for _ in ()).throw(AssertionError("headphones alias not aligned"))),
        ("growth_decline_sets_correct", lambda: sorted(_run()[1].get("growth_products", [])) == sorted(expected.loc[expected["trend"] == "growth", "canonical_product"].tolist()) and sorted(_run()[1].get("decline_products", [])) == sorted(expected.loc[expected["trend"] == "decline", "canonical_product"].tolist()) or (_ for _ in ()).throw(AssertionError("growth/decline classification incorrect"))),
        ("no_false_new_product_labels", lambda: coverage >= 0.9 and _run()[1].get("coverage_ratio", 0) >= 0.9 or (_ for _ in ()).throw(AssertionError("key misalignment treated products as new"))),
        ("records_match_expected", lambda: _records_match_expected() or (_ for _ in ()).throw(AssertionError("comparison output does not match expected aligned records"))),
    ])
    return emit_report("E3-LS3-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
