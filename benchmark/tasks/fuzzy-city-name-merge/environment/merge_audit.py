from __future__ import annotations

import pandas as pd


def build_unmatched_report(merged: pd.DataFrame) -> dict:
    population_missing = merged.loc[merged["gdp_billion"].isna(), "city_population"].tolist()
    gdp_missing = merged.loc[merged["population"].isna(), "city_gdp"].tolist()
    return {
        "population_without_gdp": population_missing,
        "gdp_without_population": gdp_missing,
    }
