from __future__ import annotations

import pandas as pd

NULL_MARKERS = {"", "n/a", "null", "-"}


def clean_amount_series(series: pd.Series) -> pd.Series:
    normalized = (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    normalized = normalized.where(~normalized.str.lower().isin(NULL_MARKERS), other=None)
    return pd.to_numeric(normalized, errors="coerce")
