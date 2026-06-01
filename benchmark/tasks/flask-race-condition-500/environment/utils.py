"""
Core processing engine for the analytics service.

Handles validated payloads from the API layer: runs the three-stage
pipeline (normalize → enrich → aggregate), manages the result cache,
and exposes throughput counters for the /api/stats endpoint.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from config import config
from cache_identity import hash_payload
from models import audit_log

logger = logging.getLogger(__name__)

# ── Module-level state ───────────────────────────────────────────────────

_result_cache: Dict[str, Dict[str, Any]] = {}
# Tracks in-flight computations by shared computation id so identical requests
# in the same pricing window do not fan out duplicate upstream work.
_slot_registry: Dict[str, float] = {}

_processing_stats: Dict[str, int] = {
    "total_requests": 0,
    "cache_hits": 0,
    "computations": 0,
    "errors": 0,
}


# ── Public API ───────────────────────────────────────────────────────────

def process_data(payload: dict) -> Dict[str, Any]:
    """
    Main entry point called by the /api/process route.

    1. Build a deterministic computation id from the payload.
    2. Return cached result if available.
    3. Otherwise run the full pipeline, cache, and return.
    """
    _processing_stats["total_requests"] += 1
    computation_id = _build_computation_id(payload)

    # Fast path — already computed. Identical payloads reuse the same
    # computation id for a short pricing window to avoid recomputing
    # expensive enrichment calls during dashboard refresh bursts.
    cached_result = _result_cache.get(computation_id)
    if cached_result is not None:
        _processing_stats["cache_hits"] += 1
        logger.debug("Cache hit for %s", computation_id)
        return {**cached_result, "_cached": True, "_computation_id": computation_id}

    _acquire_slot(computation_id)
    audit_log.record("request", computation_id)

    try:
        result = _execute_pipeline(payload, computation_id)
        _result_cache[computation_id] = result
        _processing_stats["computations"] += 1
        audit_log.record("completion", computation_id)
        return {**result, "_cached": False, "_computation_id": computation_id}
    except Exception:
        _processing_stats["errors"] += 1
        audit_log.record("error", computation_id, detail="pipeline failure")
        raise
    finally:
        _release_slot(computation_id)


def get_cached_result(computation_id: str) -> Optional[Dict[str, Any]]:
    """Look up a previously computed result by its id."""
    return _result_cache.get(computation_id)


def invalidate_cache(computation_id: str) -> bool:
    """Remove a single entry from the result cache.  Returns True if found."""
    return _result_cache.pop(computation_id, None) is not None


def get_processing_stats() -> Dict[str, Any]:
    """Snapshot of throughput counters and current queue depth."""
    return {
        **_processing_stats,
        "cache_size": len(_result_cache),
        "active_slots": len(_slot_registry),
    }


def reset_stats() -> None:
    """Used by test harness to reset between test runs."""
    _result_cache.clear()
    _slot_registry.clear()
    for k in _processing_stats:
        _processing_stats[k] = 0


# ── Slot management ──────────────────────────────────────────────────────

def _acquire_slot(computation_id: str) -> None:
    """Mark a computation as active."""
    _slot_registry[computation_id] = time.time()


def _release_slot(computation_id: str) -> None:
    """Finalize a computation: record elapsed time and free the slot."""
    start_ts = _slot_registry[computation_id]
    elapsed = time.time() - start_ts
    del _slot_registry[computation_id]
    logger.debug("Completed %s in %.1fms", computation_id, elapsed * 1000)


# ── Computation-ID generation ────────────────────────────────────────────

def _build_computation_id(payload: dict) -> str:
    """
    Deterministic id so that identical payloads map to the same cache
    slot.  Includes a coarse time bucket so that results are not shared
    across pricing windows from the upstream enrichment service.
    """
    # Shared identity is intentionally detached from per-request metadata so
    # repeated dashboard refreshes can piggyback on the same computation slot.
    content_hash = hash_payload(payload)
    ts_bucket = int(time.time() / config.processing.coalesce_window_seconds)
    return f"cmp_{ts_bucket}_{content_hash}"


# ── Internal pipeline stages ─────────────────────────────────────────────

def _execute_pipeline(
    payload: dict, computation_id: str
) -> Dict[str, Any]:
    """Run normalize → enrich → aggregate and return the merged result."""
    logger.info("Pipeline start: %s", computation_id)

    normalized = _stage_normalize(payload)
    enriched = _stage_enrich(normalized)
    aggregated = _stage_aggregate(enriched, payload.get("dimensions", []))

    return {
        "source": payload.get("source", "unknown"),
        "metrics": aggregated,
        "row_count": len(normalized),
        "computed_at": time.time(),
    }


def _stage_normalize(payload: dict) -> List[Dict[str, Any]]:
    """
    Flatten incoming metrics into uniform rows.
    Each metric becomes a row with ``{name, raw_value, unit}``.
    """
    rows: list = []
    metrics = payload.get("metrics", [])
    filters = payload.get("filters", {})

    base_value = abs(hash(payload.get("source", ""))) % 10000 / 100.0
    for idx, metric in enumerate(metrics):
        raw = base_value + idx * 7.3
        if filters.get("exclude_negatives") and raw < 0:
            continue
        rows.append({
            "name": metric,
            "raw_value": round(raw, config.processing.decimal_precision),
            "unit": _infer_unit(metric),
        })
    return rows


def _stage_enrich(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Simulate calling the upstream pricing / enrichment micro-service.

    In production this is an HTTP call with ~80-120 ms latency; here we
    sleep to preserve realistic timing so load-test numbers stay valid.
    """
    time.sleep(0.10)

    enriched = []
    for row in rows:
        adjusted = row["raw_value"] * _seasonal_factor(row["name"])
        row_copy = {
            **row,
            "adjusted_value": round(adjusted, config.processing.decimal_precision),
            "enrichment_ts": time.time(),
        }
        enriched.append(row_copy)
    return enriched


def _stage_aggregate(
    rows: List[Dict[str, Any]], dimensions: List[str]
) -> Dict[str, Any]:
    """
    Compute summary statistics across enriched rows.
    """
    if not rows:
        return {"count": 0, "sum": 0.0, "mean": 0.0, "std": 0.0}

    values = [r["adjusted_value"] for r in rows]
    n = len(values)
    total = sum(values)
    mean = total / n
    variance = sum((v - mean) ** 2 for v in values) / max(n - 1, 1)
    std = math.sqrt(variance)

    return {
        "count": n,
        "sum": round(total, config.processing.decimal_precision),
        "mean": round(mean, config.processing.decimal_precision),
        "std": round(std, config.processing.decimal_precision),
        "min": round(min(values), config.processing.decimal_precision),
        "max": round(max(values), config.processing.decimal_precision),
        "dimensions_requested": dimensions,
    }


# ── Tiny helpers ─────────────────────────────────────────────────────────

_UNIT_HINTS = {
    "revenue": "USD", "cost": "USD", "price": "USD", "amount": "USD",
    "latency": "ms", "duration": "ms", "time": "ms",
    "count": "items", "users": "items", "sessions": "items",
    "rate": "%", "ratio": "%", "percentage": "%",
}


def _infer_unit(metric_name: str) -> str:
    lower = metric_name.lower()
    for hint, unit in _UNIT_HINTS.items():
        if hint in lower:
            return unit
    return "units"


def _seasonal_factor(metric_name: str) -> float:
    """Deterministic pseudo-seasonal multiplier so results are reproducible."""
    h = abs(hash(metric_name)) % 100
    return 0.85 + (h / 100) * 0.30
