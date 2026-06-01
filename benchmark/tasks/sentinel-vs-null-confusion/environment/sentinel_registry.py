from __future__ import annotations

from schema_cleaner import clean_text

COMMON_MISSING = {
    "",
    "n/a",
    "na",
    "null",
    "none",
    "-1",
    "−1",
    "-999",
    "−999",
    "sensor_fault",
    "0",
    "0.0",
}


def _to_number(value: object, *, allow_decimal: bool) -> float | None:
    cleaned = clean_text(value).replace(",", ".").replace("_", "")
    if cleaned.lower() in COMMON_MISSING:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if not allow_decimal and not number.is_integer():
        return None
    return number


def clean_age(value: object) -> float | None:
    return _to_number(value, allow_decimal=False)


def clean_salary(value: object) -> float | None:
    return _to_number(value, allow_decimal=False)


def clean_temperature(value: object) -> float | None:
    return _to_number(value, allow_decimal=True)
