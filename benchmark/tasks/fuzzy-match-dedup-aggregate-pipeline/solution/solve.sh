#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "company_normalizer.py": dedent(
        """
        from __future__ import annotations

        import re

        COMPANY_ALIASES = {
            "acme": "acme corp",
            "acme corporation": "acme corp",
            "globaltech": "global tech",
            "premier sol": "premier solutions",
        }


        def canonical_company(value: str) -> str:
            normalized = str(value).strip().lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = " ".join(normalized.split())
            return COMPANY_ALIASES.get(normalized, normalized)


        def revenue_segment(annual_revenue: float) -> str:
            if annual_revenue >= 3_500_000:
                return "enterprise"
            if annual_revenue >= 1_500_000:
                return "mid_market"
            return "growth"
        """
    ),
    "process_customer_totals.py": dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path

        import pandas as pd

        from company_normalizer import canonical_company, revenue_segment
        from dedup_policy import deduplicate_crm, deduplicate_ratings

        CRM_PATH = Path("crm_contacts.csv")
        ERP_PATH = Path("erp_orders.csv")
        RATINGS_PATH = Path("external_ratings.csv")
        OUTPUT_PATH = Path("output.json")


        def _load_crm() -> pd.DataFrame:
            crm = pd.read_csv(CRM_PATH)
            crm["canonical_company"] = crm["company_name"].map(canonical_company)
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
            orders_by_company = (
                erp.groupby("canonical_company", as_index=False)["order_amount"]
                .sum()
            )
            resolved = company_dimension.merge(orders_by_company, on="canonical_company", how="left", validate="1:1")
            resolved["order_amount"] = resolved["order_amount"].fillna(0.0)

            category_totals = (
                resolved.groupby("segment", as_index=False)["order_amount"]
                .sum()
                .rename(columns={"order_amount": "total_order_amount"})
                .sort_values("segment", kind="mergesort")
                .reset_index(drop=True)
            )
            payload = {
                "row_count": int(len(resolved)),
                "coverage_ratio": round(float(resolved["order_amount"].notna().mean()), 4),
                "records": resolved.to_dict(orient="records"),
                "category_totals": category_totals.to_dict(orient="records"),
            }
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload


        if __name__ == "__main__":
            run()
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
