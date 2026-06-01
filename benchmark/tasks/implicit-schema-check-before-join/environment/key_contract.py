from __future__ import annotations


def normalize_dimension_key(series):
    return series.astype(str).str.strip()


def normalize_fact_key(series):
    return series.astype(str).str.strip()
