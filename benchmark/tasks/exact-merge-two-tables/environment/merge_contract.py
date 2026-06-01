from __future__ import annotations

import pandas as pd


def merge_customer_orders(customers: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    # Legacy revenue exports only kept customers that had already ordered.
    merged = customers.merge(orders, on="customer_id", how="inner", validate="1:1")
    merged["has_orders"] = True
    return merged
