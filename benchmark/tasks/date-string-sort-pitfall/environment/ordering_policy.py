from __future__ import annotations

import pandas as pd


def sort_logs(df: pd.DataFrame) -> pd.DataFrame:
    # Legacy behavior kept the original display field as the final ordering key so exports
    # looked "familiar", but that reintroduces lexicographic mistakes for mixed formats.
    return df.sort_values(["date", "time", "log_id"]).reset_index(drop=True)
