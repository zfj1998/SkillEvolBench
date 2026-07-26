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
SCRIPT = PROJECT / "process_customer_totals.py"
CRM = PROJECT / "crm_contacts.csv"
ERP = PROJECT / "erp_orders.csv"
RATINGS = PROJECT / "external_ratings.csv"
OUTPUT = PROJECT / "output.json"


def _canonical_company(value: str) -> str:
    normalized = str(value).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    aliases = {
        "acme": "acme corp",
        "acme corporation": "acme corp",
        "globaltech": "global tech",
        "premier sol": "premier solutions",
    }
    return aliases.get(normalized, normalized)


def _segment(value: float) -> str:
    if value >= 3_500_000:
        return "enterprise"
    if value >= 1_500_000:
        return "mid_market"
    return "growth"


def _expected():
    crm = pd.read_csv(CRM)
    crm["canonical_company"] = crm["company_name"].map(_canonical_company)
    crm["segment"] = crm["annual_revenue"].astype(float).map(_segment)
    crm = crm.drop_duplicates(subset=["canonical_company"], keep="first")

    ratings = pd.read_csv(RATINGS)
    ratings["canonical_company"] = ratings["company"].map(_canonical_company)
    ratings = ratings.drop_duplicates(subset=["canonical_company"], keep="first")

    erp = pd.read_csv(ERP)
    erp["canonical_company"] = erp["company_name"].map(_canonical_company)
    erp["order_amount"] = erp["order_amount"].astype(float)
    erp = erp.groupby("canonical_company", as_index=False)["order_amount"].sum()

    merged = crm.merge(ratings, on="canonical_company", how="left", validate="1:1").merge(erp, on="canonical_company", how="left", validate="1:1")
    merged["order_amount"] = merged["order_amount"].fillna(0.0)
    category_totals = (
        merged.groupby("segment", as_index=False)["order_amount"]
        .sum()
        .rename(columns={"order_amount": "total_order_amount"})
        .sort_values("segment", kind="mergesort")
        .reset_index(drop=True)
    )
    return merged, category_totals


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def _records_by_key(records, key):
    """Treat JSON array order as presentation unless the contract says otherwise."""
    return {item[key]: item for item in records}


def run():
    merged, category_totals = _expected()
    public = run_checks("public", [
        ("non_empty_output", lambda: len(_run()[1].get("records", [])) > 0 or (_ for _ in ()).throw(AssertionError("merged dataset missing"))),
        ("category_totals_present", lambda: len(_run()[1].get("category_totals", [])) > 0 or (_ for _ in ()).throw(AssertionError("category totals missing"))),
    ])
    hidden = run_checks("hidden", [
        ("coverage_above_90pct", lambda: len(_run()[1].get("records", [])) >= int(len(merged) * 0.9) or (_ for _ in ()).throw(AssertionError("merged coverage below 90%"))),
        ("no_fanout", lambda: _run()[1].get("row_count", 0) == len(merged) or (_ for _ in ()).throw(AssertionError("fanout detected in merged dataset"))),
        (
            "category_totals_correct",
            lambda: _records_by_key(
                _run()[1].get("category_totals", []), "segment"
            )
            == _records_by_key(category_totals.to_dict(orient="records"), "segment")
            or (_ for _ in ()).throw(AssertionError("category totals incorrect")),
        ),
        (
            "records_match_ground_truth",
            lambda: _records_by_key(
                _run()[1].get("records", []), "canonical_company"
            )
            == _records_by_key(
                merged.to_dict(orient="records"), "canonical_company"
            )
            or (_ for _ in ()).throw(
                AssertionError("multi-source merge output incorrect")
            ),
        ),
    ])
    return emit_report("E3-LS3-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
