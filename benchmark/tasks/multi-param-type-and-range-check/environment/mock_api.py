TRACE = []


def fetch_weather(city, days, units):
    TRACE.append({"city": city, "days": days, "units": units})
    if not city or not isinstance(city, str) or not city.strip():
        raise ValueError("city invalid")
    if not isinstance(days, int) or days < 1 or days > 14:
        raise ValueError("days invalid")
    if units not in {"metric", "imperial"}:
        raise ValueError("units invalid")
    return {"city": city, "forecast_days": days, "units": units}
