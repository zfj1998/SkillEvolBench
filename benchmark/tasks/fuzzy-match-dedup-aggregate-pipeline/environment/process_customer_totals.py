from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from city_alignment import canonical_city
from company_normalizer import canonical_company, revenue_segment
from dedup_policy import deduplicate_crm, deduplicate_ratings

CRM_PATH = Path("crm_contacts.csv")
ERP_PATH = Path("erp_orders.csv")
RATINGS_PATH = Path("external_ratings.csv")
OUTPUT_PATH = Path("output.json")


def _load_crm() -> pd.DataFrame:
    crm = pd.read_csv(CRM_PATH)
    crm["canonical_company"] = crm["company_name"].map(canonical_company)
    crm["canonical_city"] = crm["city"].map(canonical_city)
    crm["segment"] = crm["annual_revenue"].astype(float).map(revenue_segment)
    return deduplicate_crm(crm)


def _load_erp() -> pd.DataFrame:
    erp = pd.read_csv(ERP_PATH)
    erp["canonical_company"] = erp["company_name"].map(canonical_company)
    erp["order_amount"] = erp["order_amount"].astype(float)
    return erp


def _load_ratings() -> pd.DataFrame:
    ratings = pd.read_csv(RATINGS_PATH)
    ratings["canonical_company"] = ratings["company"].map(canonical_company)
    return deduplicate_ratings(ratings)


def run(output_path: Path = OUTPUT_PATH) -> dict:
    crm = _load_crm()
    erp = _load_erp()
    ratings = _load_ratings()

    company_dimension = crm.merge(ratings, on="canonical_company", how="left", validate="1:1")
    named_orders = erp.merge(company_dimension, on="canonical_company", how="left")
    unresolved_orders = named_orders[named_orders["segment"].isna()].drop(columns=company_dimension.columns.difference(["canonical_city", "segment", "canonical_company", "city"]))
    city_fallback = unresolved_orders.merge(company_dimension, on="canonical_city", how="left")
    resolved = pd.concat([named_orders[named_orders["segment"].notna()], city_fallback], ignore_index=True, sort=False)

    category_totals = (
        resolved.groupby("segment", as_index=False)["order_amount"]
        .sum()
        .rename(columns={"order_amount": "total_order_amount"})
        .sort_values("segment", kind="mergesort")
        .reset_index(drop=True)
    )
    payload = {
        "row_count": int(len(resolved)),
        "coverage_ratio": round(float(resolved["segment"].notna().mean()), 4),
        "records": resolved.to_dict(orient="records"),
        "category_totals": category_totals.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
