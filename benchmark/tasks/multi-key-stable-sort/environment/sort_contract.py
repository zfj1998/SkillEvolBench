from __future__ import annotations


def attach_feed_order(df):
    df = df.copy()
    df["_feed_order"] = range(len(df))
    return df
