from __future__ import annotations

import pandas as pd


def parse_display_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")
