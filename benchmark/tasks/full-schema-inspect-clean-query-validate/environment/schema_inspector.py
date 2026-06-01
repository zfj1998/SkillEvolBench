from __future__ import annotations


def apply_canonical_headers(df):
    df = df.copy()
    df.columns = [str(column).replace("\ufeff", "").strip().lower() for column in df.columns]
    return df
