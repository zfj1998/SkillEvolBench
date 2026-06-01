from __future__ import annotations

import pandas as pd


def classify_temperature_readings(temperatures: pd.Series) -> dict[str, int]:
    offline_mask = temperatures.isna() | (temperatures == 0)
    return {
        "offline_reading_count": int(offline_mask.sum()),
        "zero_degree_count": int((temperatures == 0).sum()),
    }
