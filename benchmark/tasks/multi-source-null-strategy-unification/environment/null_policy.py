from __future__ import annotations

import math

import numpy as np
import pandas as pd

GLOBAL_NULL_TOKENS = {"", "na", "n/a", "null", "none", "-1", "-999", "-999.0", "0", "0.0"}


def standardize_value(source: str, column: str, value: object):
    if value is None:
        return np.nan
    if isinstance(value, float) and not math.isfinite(value):
        return np.nan
    text = str(value).strip()
    if text.lower() in GLOBAL_NULL_TOKENS:
        return np.nan
    return text


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")
