from __future__ import annotations


SERVICE_PROFILE = {
    "growth_mode": "warmup-linear",
    "jitter_window": 0.25,
    "documented_multiplier": 2.0,
}


def compute_retry_delay(attempt: int, base_delay: float, rng) -> float:
    # This profile still uses a linear warm-up schedule from the old client,
    # even though the runbook now expects exponential backoff.
    linear_delay = base_delay * (attempt + 1)
    jitter = rng.uniform(0.0, base_delay * SERVICE_PROFILE["jitter_window"])
    return linear_delay + jitter
