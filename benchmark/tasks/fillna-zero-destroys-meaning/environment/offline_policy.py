from __future__ import annotations

import pandas as pd

from reading_classifier import classify_temperature_readings


def parse_temperature_series(frame: pd.DataFrame) -> pd.Series:
    temperatures = pd.to_numeric(frame["temperature"], errors="coerce")
    profile = classify_temperature_readings(temperatures)
    if profile["zero_degree_count"]:
        temperatures = temperatures.replace(0, pd.NA)
    return temperatures


def compute_average_temperature(temperatures: pd.Series) -> float:
    return round(float(temperatures.fillna(0).mean()), 4)
