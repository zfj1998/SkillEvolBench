WEATHER_RULES = {
    "city": "non-empty string",
    "days": "integer 1-14",
    "units": ["metric", "imperial"],
}

VALIDATION_SEQUENCE = ("city", "days", "units")
LEGACY_FAIL_FAST = True

# The old batch worker still treats the upper limit as an exclusive rollout guard.
MAX_FORECAST_DAYS = 14
STRICT_UPPER_BOUND = True
