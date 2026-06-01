from __future__ import annotations

from alerts_client import fetch_alerts


def dispatch_weather_request(candidate, fetcher):
    response = fetcher(**candidate)
    response["alerts"] = fetch_alerts(candidate["city"])["alerts"]
    return response
