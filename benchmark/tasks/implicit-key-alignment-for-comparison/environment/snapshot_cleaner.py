from __future__ import annotations

import re

import pandas as pd

from product_aliases import PRODUCT_ALIASES


def canonical_product_name(value: str) -> str:
    normalized = str(value).replace("\u200b", "").strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return PRODUCT_ALIASES.get(normalized, normalized)


def prepare_snapshot(df: pd.DataFrame, revenue_column: str = "revenue") -> pd.DataFrame:
    prepared = df.copy()
    prepared["canonical_product"] = prepared["product_name"].map(canonical_product_name)
    prepared[revenue_column] = pd.to_numeric(
        prepared[revenue_column]
        .astype(str)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )
    prepared["snapshot_rank"] = prepared["snapshot_id"].astype(str)
    prepared = prepared.sort_values(["canonical_product", "snapshot_rank"], kind="mergesort")
    prepared = prepared.drop_duplicates(subset=["canonical_product"], keep="last").copy()
    return prepared
