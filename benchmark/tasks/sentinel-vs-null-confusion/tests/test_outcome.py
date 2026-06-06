from __future__ import annotations

import json
import subprocess
import sys
import unicodedata
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "summarize_employee_metrics.py"
DATA = PROJECT / "employee_data.csv"
OUTPUT = PROJECT / "output.json"


def _clean_text(value: object) -> str:
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    text = text.strip().strip('"').strip("'").strip()
    return " ".join(text.split())


def _normalize_header(header: object) -> str:
    return _clean_text(header).lower().replace(" ", "_")


def _parse_age(value: object) -> float | None:
    cleaned = _clean_text(value).lower()
    if cleaned in {"", "n/a", "na", "null", "none", "-1", "−1"}:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return number if number.is_integer() else None


def _parse_salary(value: object) -> float | None:
    cleaned = _clean_text(value).lower().replace(",", "").replace("_", "")
    if cleaned in {"", "n/a", "na", "null", "none"}:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return number if number.is_integer() else None


def _parse_temperature(value: object) -> float | None:
    cleaned = _clean_text(value).lower()
    if cleaned in {"", "n/a", "na", "null", "none", "-999", "-999.0", "−999", "sensor_fault"}:
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _expected() -> dict:
    frame = pd.read_csv(DATA, keep_default_na=False)
    frame.columns = [_normalize_header(column) for column in frame.columns]
    frame["age_clean"] = frame["age"].map(_parse_age)
    frame["salary_clean"] = frame["salary"].map(_parse_salary)
    frame["temperature_clean"] = frame["site_temperature"].map(_parse_temperature)
    return {
        "average_age": round(float(pd.Series(frame["age_clean"]).dropna().mean()), 4),
        "average_salary": round(float(pd.Series(frame["salary_clean"]).dropna().mean()), 4),
        "average_temperature": round(float(pd.Series(frame["temperature_clean"]).dropna().mean()), 4),
        "age_missing": int(pd.Series(frame["age_clean"]).isna().sum()),
        "salary_zero_count": int((pd.Series(frame["salary_clean"]).fillna(-1) == 0).sum()),
        "salary_missing": int(pd.Series(frame["salary_clean"]).isna().sum()),
        "temperature_missing": int(pd.Series(frame["temperature_clean"]).isna().sum()),
    }


def _run() -> tuple[subprocess.CompletedProcess[str], dict]:
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    public = run_checks("public", [
        ("all_metrics_present", lambda: all(key in _run()[1] for key in ["average_age", "average_salary", "average_temperature"]) or (_ for _ in ()).throw(AssertionError("missing output metrics"))),
    ])
    hidden = run_checks("hidden", [
        ("age_average_correct", lambda: abs(_run()[1].get("average_age", 0.0) - expected["average_age"]) <= 0.01 or (_ for _ in ()).throw(AssertionError("age average incorrect"))),
        ("salary_average_keeps_zero", lambda: abs(_run()[1].get("average_salary", 0.0) - expected["average_salary"]) <= 0.01 or (_ for _ in ()).throw(AssertionError("salary average dropped valid zero salaries"))),
        ("temperature_average_correct", lambda: abs(_run()[1].get("average_temperature", 0.0) - expected["average_temperature"]) <= 0.01 or (_ for _ in ()).throw(AssertionError("temperature average incorrect"))),
        ("salary_zero_count_preserved", lambda: _run()[1].get("valid_counts", {}).get("salary_zero_count") == expected["salary_zero_count"] or (_ for _ in ()).throw(AssertionError("salary=0 rows were not preserved"))),
        ("sentinel_counts_present", lambda: set(_run()[1].get("sentinel_counts", {}).keys()) == {"age_missing", "salary_missing", "temperature_missing"} or (_ for _ in ()).throw(AssertionError("sentinel count metadata missing"))),
        ("sentinel_counts_correct", lambda: _run()[1].get("sentinel_counts", {}) == {"age_missing": expected["age_missing"], "salary_missing": expected["salary_missing"], "temperature_missing": expected["temperature_missing"]} or (_ for _ in ()).throw(AssertionError("sentinel counts incorrect"))),
    ])
    return emit_report("E3-LS4-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
