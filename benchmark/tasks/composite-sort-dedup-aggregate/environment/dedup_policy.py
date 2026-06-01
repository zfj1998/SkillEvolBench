from __future__ import annotations

import pandas as pd


def deduplicate_transactions(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(subset=["transaction_id"]).copy()
