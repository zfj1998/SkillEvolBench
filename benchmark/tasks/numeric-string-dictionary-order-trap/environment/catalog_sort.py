from __future__ import annotations

import pandas as pd


def order_catalog(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(["product_id_normalized", "name"], ascending=[True, True], kind="mergesort").reset_index(drop=True)
