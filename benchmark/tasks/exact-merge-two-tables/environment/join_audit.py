from __future__ import annotations

import pandas as pd


def summarize_unmatched_customers(merged: pd.DataFrame) -> dict:
    missing_mask = merged["total_orders"].isna() if "total_orders" in merged.columns else pd.Series(False, index=merged.index)
    return {
        "missing_count": int(missing_mask.sum()),
        "missing_customer_ids": merged.loc[missing_mask, "customer_id"].astype(int).tolist()[:10],
    }
