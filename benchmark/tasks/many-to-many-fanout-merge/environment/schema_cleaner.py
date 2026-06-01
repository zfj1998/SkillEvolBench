from __future__ import annotations

import re

import pandas as pd


def _clean_string(value: object) -> str:
    cleaned = str(value).replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [_clean_string(column).lower().replace(" ", "_") for column in cleaned.columns]
    return cleaned


def clean_students(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = _clean_columns(df)
    cleaned["student_id"] = pd.to_numeric(cleaned["student_id"].map(_clean_string), errors="coerce")
    cleaned = cleaned.dropna(subset=["student_id"]).copy()
    cleaned["student_id"] = cleaned["student_id"].astype(int)
    cleaned["name"] = cleaned["name"].map(_clean_string)
    major_map = {"cs": "computer science"}
    cleaned["major"] = cleaned["major"].map(lambda value: major_map.get(_clean_string(value).lower(), _clean_string(value).lower()))
    return cleaned.drop_duplicates(subset=["student_id"], keep="first").copy()


def clean_enrollments(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = _clean_columns(df)
    cleaned["student_id"] = pd.to_numeric(cleaned["student_id"].map(_clean_string), errors="coerce")
    cleaned["course_id"] = pd.to_numeric(cleaned["course_id"].map(_clean_string), errors="coerce")
    cleaned = cleaned.dropna(subset=["student_id", "course_id"]).copy()
    cleaned["student_id"] = cleaned["student_id"].astype(int)
    cleaned["course_id"] = cleaned["course_id"].astype(int)
    cleaned["semester"] = cleaned["semester"].map(_clean_string)
    cleaned["grade"] = cleaned["grade"].map(_clean_string)
    return cleaned


def clean_courses(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = _clean_columns(df)
    cleaned["course_id"] = pd.to_numeric(cleaned["course_id"].map(_clean_string), errors="coerce")
    cleaned = cleaned.dropna(subset=["course_id"]).copy()
    cleaned["course_id"] = cleaned["course_id"].astype(int)
    cleaned["course_name"] = cleaned["course_name"].map(_clean_string)
    cleaned["department"] = cleaned["department"].map(lambda value: _clean_string(value).lower())
    cleaned["credits"] = cleaned["credits"].map(_clean_string).astype(int)
    return cleaned.drop_duplicates(subset=["course_id"], keep="first").copy()
