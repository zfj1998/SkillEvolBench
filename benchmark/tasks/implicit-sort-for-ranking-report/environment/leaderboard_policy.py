from __future__ import annotations

import pandas as pd


def build_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    ranked = (
        df.groupby("salesperson", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "total_sales"})
        .nlargest(10, "total_sales")
    )
    return ranked.sort_values(["total_sales", "salesperson"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
