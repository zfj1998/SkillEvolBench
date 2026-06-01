from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from schema_cleaner import normalize_header
from sentinel_registry import clean_age, clean_salary, clean_temperature

INPUT_PATH = Path("employee_data.csv")
OUTPUT_PATH = Path("output.json")


def run(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    frame = pd.read_csv(input_path, keep_default_na=False)
    frame.columns = [normalize_header(column) for column in frame.columns]
    frame["age_clean"] = frame["age"].map(clean_age)
    frame["salary_clean"] = frame["salary"].map(clean_salary)
    frame["temperature_clean"] = frame["site_temperature"].map(clean_temperature)

    payload = {
        "average_age": round(float(pd.Series(frame["age_clean"]).dropna().mean()), 4),
        "average_salary": round(float(pd.Series(frame["salary_clean"]).dropna().mean()), 4),
        "average_temperature": round(float(pd.Series(frame["temperature_clean"]).dropna().mean()), 4),
        "sentinel_counts": {
            "age_missing": int(pd.Series(frame["age_clean"]).isna().sum()),
            "salary_missing": int(pd.Series(frame["salary_clean"]).isna().sum()),
            "temperature_missing": int(pd.Series(frame["temperature_clean"]).isna().sum()),
        },
        "valid_counts": {
            "age": int(pd.Series(frame["age_clean"]).dropna().shape[0]),
            "salary": int(pd.Series(frame["salary_clean"]).dropna().shape[0]),
            "temperature": int(pd.Series(frame["temperature_clean"]).dropna().shape[0]),
            "salary_zero_count": int((pd.Series(frame["salary_clean"]).fillna(-1) == 0).sum()),
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
