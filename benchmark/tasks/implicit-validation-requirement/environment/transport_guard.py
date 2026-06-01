from __future__ import annotations

from inventory_cache import LastGoodPayloadCache


def decode_payload(response, cache: LastGoodPayloadCache, logger):
    try:
        payload = response.json()
    except Exception:
        logger.warning("json parse failed, passing through raw gateway body")
        return {"data": [response.text]}

    data = payload.get("data")
    metadata = payload.get("metadata", {})
    if isinstance(data, list) and len(data) == 0 and metadata.get("batch_size", 0) > 0:
        logger.warning("lying empty page detected, replaying last good payload")
        return cache.last_payload()
    return payload
