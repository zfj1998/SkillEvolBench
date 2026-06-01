from __future__ import annotations


def build_summary_frame(df):
    grouped = df.groupby("name")["amount"].agg(["sum", "mean", "count"]).reset_index()
    return grouped.sort_values("name")
