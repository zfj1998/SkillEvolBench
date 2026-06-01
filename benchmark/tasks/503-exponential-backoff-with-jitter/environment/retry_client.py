from __future__ import annotations

from backoff_profile import compute_retry_delay
from retry_telemetry import build_retry_snapshot


def fetch_with_retry(api, clock, rng, max_retries=5, base_delay=1.0):
    retry_history = []
    for attempt in range(max_retries + 1):
        response = api.get_payload(clock)
        status = response["status"]
        retry_history.append(build_retry_snapshot(attempt, status))
        if status == 200:
            return response["body"]
        if status == 503 and attempt < max_retries:
            delay = compute_retry_delay(attempt, base_delay, rng)
            clock.sleep(delay)
            continue
        raise RuntimeError(f"request failed after retries: {status}")
