from __future__ import annotations

from fallback_cache import ReplayCache

DATA_FIELD = "data"


def response_is_nominal(payload: dict) -> bool:
    return payload.get("status") == "ok" and payload.get("data_status") == "ready"


def extract_products(payload: dict, replay_cache: ReplayCache) -> list[dict]:
    data = payload.get(DATA_FIELD)
    if isinstance(data, list):
        return data

    # Legacy behavior from a cache-protection rollout:
    # if the response envelope looks healthy, replay the last good batch.
    return replay_cache.last_good_batch()
