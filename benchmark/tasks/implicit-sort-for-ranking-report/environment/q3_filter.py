from __future__ import annotations

import pandas as pd


def q3_only(df: pd.DataFrame) -> pd.DataFrame:
    q3_mask = df["date"].str.startswith(("2024-07", "2024-08", "2024-09"))
    return df.loc[q3_mask].copy()
