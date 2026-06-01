from __future__ import annotations

import pandas as pd


def deduplicate_crm(crm: pd.DataFrame) -> pd.DataFrame:
    return crm.drop_duplicates(subset=["canonical_company"], keep="first").copy()


def deduplicate_ratings(ratings: pd.DataFrame) -> pd.DataFrame:
    return ratings.drop_duplicates(subset=["canonical_company"], keep="first").copy()
