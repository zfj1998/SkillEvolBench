from __future__ import annotations

import pandas as pd


def merge_orders(users: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    merged = pd.merge(users, orders, on="user_id", how="inner")
    return merged


def build_region_totals(merged: pd.DataFrame) -> dict[str, float]:
    if merged.empty:
        return {}
    return (
        merged.groupby("region")["amount"].sum().round(2).sort_index().to_dict()
    )
