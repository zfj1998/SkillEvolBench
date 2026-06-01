from __future__ import annotations

from validation_contract import (
    LEGACY_FAIL_FAST,
    MAX_FORECAST_DAYS,
    STRICT_UPPER_BOUND,
    VALIDATION_SEQUENCE,
    WEATHER_RULES,
)


def prepare_candidate(request):
    candidate = dict(request)
    city = candidate.get("city")
    if isinstance(city, str):
        candidate["city"] = city.strip()
    return candidate


def _validate_city(candidate):
    city = candidate.get("city")
    if city is None or (isinstance(city, str) and not city):
        return {"param": "city", "error": "required", "value": city, "expected": WEATHER_RULES["city"]}
    if not isinstance(city, str):
        return {"param": "city", "error": "type", "value": city, "expected": WEATHER_RULES["city"]}
    return None


def _validate_days(candidate):
    days = candidate.get("days")
    if not isinstance(days, int):
        return {"param": "days", "error": "type", "value": days, "expected": WEATHER_RULES["days"]}
    max_allowed = MAX_FORECAST_DAYS - 1 if STRICT_UPPER_BOUND else MAX_FORECAST_DAYS
    if days < 1 or days > max_allowed:
        return {"param": "days", "error": "range", "value": days, "expected": WEATHER_RULES["days"]}
    return None


def _validate_units(candidate):
    units = candidate.get("units")
    if units not in {"metric", "imperial"}:
        return {"param": "units", "error": "enum", "value": units, "expected": WEATHER_RULES["units"]}
    return None


VALIDATORS = {
    "city": _validate_city,
    "days": _validate_days,
    "units": _validate_units,
}


def collect_validation_errors(candidate):
    errors = []
    for field_name in VALIDATION_SEQUENCE:
        validator = VALIDATORS[field_name]
        error = validator(candidate)
        if error:
            errors.append(error)
            if LEGACY_FAIL_FAST:
                break
    return errors
