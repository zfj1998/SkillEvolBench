from __future__ import annotations

import pandas as pd


def build_source_null_summary(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for source, group in frame.groupby("source", dropna=False):
        summary[str(source)] = {
            "missing_price": int(group["price"].isna().sum()),
            "missing_stock": int(group["stock"].isna().sum()),
            "out_of_stock_count": int((group["stock"] == 0).sum()),
        }
    return summary


def build_category_totals(frame: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    payload: dict[str, dict[str, float | int]] = {}
    for category, group in frame.groupby("category", dropna=False):
        valid_price = group["price"].dropna()
        payload[str(category)] = {
            "valid_price_count": int(valid_price.shape[0]),
            "average_price": round(float(valid_price.mean()), 2) if not valid_price.empty else None,
            "total_stock": int(group["stock"].dropna().sum()),
        }
    return payload
