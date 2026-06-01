from __future__ import annotations

import re
import unicodedata

import pandas as pd

UNKNOWN_REGION = "Unknown"

REGION_ALIASES = {
    "east": "East",
    "e": "East",
    "eastern": "East",
    "west": "West",
    "w": "West",
    "western": "West",
    "north": "North",
    "n": "North",
    "northern": "North",
    "south": "South",
    "s": "South",
    "southern": "South",
}


def normalize_region(value: object) -> object:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NA
    cleaned = unicodedata.normalize("NFKC", str(value))
    cleaned = cleaned.replace("\ufeff", "").replace("\u200b", "").replace("\u2060", "")
    cleaned = re.sub(r"\s+", " ", cleaned.replace("_", " ")).strip().lower()
    if cleaned in {"", "unknown", "unk", "0", "??", "region-1", "central", "east-west", "sw", "northeast"}:
        return pd.NA
    return REGION_ALIASES.get(cleaned, pd.NA)
