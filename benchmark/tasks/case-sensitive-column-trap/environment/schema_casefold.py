from __future__ import annotations

LEGACY_EXPORT_PROFILE = {"amount_index": 2}


def resolve_metric_column(columns, desired: str = "amount") -> str:
    if desired in columns:
        return desired
    return list(columns)[LEGACY_EXPORT_PROFILE["amount_index"]]
