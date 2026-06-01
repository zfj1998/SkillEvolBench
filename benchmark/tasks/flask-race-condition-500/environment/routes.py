"""
API route definitions for the analytics processing service.

All endpoints are registered on a Flask Blueprint so that app.py can
mount them under any prefix.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Callable

from flask import Blueprint, Response, jsonify, request

from models import ProcessingResult, validate_processing_request
from utils import (
    get_cached_result,
    get_processing_stats,
    invalidate_cache,
    process_data,
)

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__, url_prefix="/api")


# ── Middleware / decorators ──────────────────────────────────────────────

def _request_timer(fn: Callable) -> Callable:
    """Inject X-Duration-Ms header and log slow requests (>500 ms)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        t0 = time.time()
        response = fn(*args, **kwargs)
        duration_ms = (time.time() - t0) * 1000
        if isinstance(response, Response):
            response.headers["X-Duration-Ms"] = f"{duration_ms:.1f}"
        if duration_ms > 500:
            logger.warning(
                "Slow request: %s %s took %.0f ms",
                request.method, request.path, duration_ms,
            )
        return response

    return wrapper


# ── Endpoints ────────────────────────────────────────────────────────────

@api.route("/process", methods=["POST"])
@_request_timer
def handle_process():
    """
    Accept a processing payload, run the pipeline (or return cached),
    and respond with the computed result.
    """
    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    try:
        validated = validate_processing_request(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Pass only computation-relevant fields; request metadata stays in
    # the route layer and is not part of the cache key.
    computation_payload = {
        "source": validated.source,
        "metrics": validated.metrics,
        "dimensions": validated.dimensions,
        "filters": validated.filters,
    }
    start = time.time()
    result = process_data(computation_payload)               # ← traceback surfaces here
    duration_ms = (time.time() - start) * 1000

    response_body = ProcessingResult(
        request_id=validated.request_id,
        computation_id=result.get("_computation_id", ""),
        data={k: v for k, v in result.items() if not k.startswith("_")},
        cached=result.get("_cached", False),
        duration_ms=round(duration_ms, 2),
    ).to_response()

    return jsonify(response_body), 200


@api.route("/results/<computation_id>", methods=["GET"])
@_request_timer
def handle_get_result(computation_id: str):
    """Retrieve a previously computed result from cache."""
    result = get_cached_result(computation_id)
    if result is None:
        return jsonify({"error": "Result not found", "computation_id": computation_id}), 404
    return jsonify({"computation_id": computation_id, "data": result}), 200


@api.route("/results/<computation_id>", methods=["DELETE"])
@_request_timer
def handle_invalidate(computation_id: str):
    """Remove a cached result (e.g. after upstream data correction)."""
    removed = invalidate_cache(computation_id)
    status = 200 if removed else 404
    return jsonify({"computation_id": computation_id, "removed": removed}), status


@api.route("/stats", methods=["GET"])
@_request_timer
def handle_stats():
    """Real-time throughput and cache statistics."""
    return jsonify(get_processing_stats()), 200


@api.route("/health", methods=["GET"])
def handle_health():
    """
    Liveness probe for Kubernetes.  Returns 200 as long as the process
    is running — readiness checks are handled separately by the infra
    layer.
    """
    return jsonify({"status": "ok", "timestamp": time.time()}), 200


# ── Blueprint-level error handlers ───────────────────────────────────────

@api.errorhandler(400)
def bad_request(exc):
    return jsonify({"error": "Bad request", "detail": str(exc)}), 400


@api.errorhandler(404)
def not_found(exc):
    return jsonify({"error": "Not found"}), 404


@api.errorhandler(500)
def internal_error(exc):
    logger.exception("Unhandled exception on %s %s", request.method, request.path)
    return jsonify({"error": "Internal server error"}), 500
