from __future__ import annotations

import pandas as pd


def order_employees(df: pd.DataFrame) -> pd.DataFrame:
    # Legacy report generator added hire_date as a deterministic tie-breaker, but the
    # downstream requirement is to preserve original feed order for ties instead.
    return df.sort_values(
        ["department", "salary", "hire_date"],
        ascending=[True, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
