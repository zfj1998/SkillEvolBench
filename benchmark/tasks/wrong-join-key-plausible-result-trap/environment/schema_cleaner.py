from __future__ import annotations

import re

import pandas as pd


def _clean_string(value: object) -> str:
    cleaned = str(value).replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def clean_users(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [_clean_string(column).lower() for column in cleaned.columns]
    cleaned["id"] = pd.to_numeric(cleaned["id"].map(_clean_string), errors="coerce")
    cleaned["name"] = cleaned["name"].map(_clean_string)
    cleaned = cleaned.dropna(subset=["id", "name"])
    cleaned["id"] = cleaned["id"].astype(int)
    cleaned["email"] = cleaned["email"].map(_clean_string)
    cleaned["plan"] = cleaned["plan"].map(lambda value: _clean_string(value).lower())
    return cleaned


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [_clean_string(column).lower() for column in cleaned.columns]
    cleaned["id"] = pd.to_numeric(cleaned["id"].map(_clean_string), errors="coerce")
    cleaned["user_id"] = pd.to_numeric(cleaned["user_id"].map(_clean_string), errors="coerce")
    cleaned["amount"] = pd.to_numeric(
        cleaned["amount"]
        .map(_clean_string)
        .astype(str)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )
    cleaned = cleaned.dropna(subset=["id", "user_id"])
    cleaned = cleaned.dropna(subset=["amount"])
    cleaned["id"] = cleaned["id"].astype(int)
    cleaned["user_id"] = cleaned["user_id"].astype(int)
    return cleaned
