"""
Outcome verifier for E1-LS1-T1: flask-race-condition-500

Tests are split into two groups:
  - Public  (P1-P5):  provided to the agent, verify basic single-request correctness.
  - Hidden  (H1-H8):  NOT shown to agent, verify concurrency safety and robustness.

All tests must pass for the oracle solution.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from app import create_app
from utils import reset_stats


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def app():
    application = create_app(testing=True)
    reset_stats()
    return application


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c


def _post(client, payload):
    resp = client.post(
        "/api/process",
        data=json.dumps(payload),
        content_type="application/json",
    )
    return resp.status_code, resp.get_json()


def _valid_payload(source="web_analytics", metrics=None):
    return {
        "source": source,
        "metrics": ["revenue", "page_views", "session_duration"] if metrics is None else metrics,
        "dimensions": ["country"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Public tests (P1-P5) — provided to agent
# ═══════════════════════════════════════════════════════════════════════════

class TestPublic:
    """Basic single-request correctness — these tests are visible to the agent."""

    def test_p1_valid_request_returns_200(self, client):
        """A well-formed payload should return 200 with computed data."""
        status, body = _post(client, _valid_payload())
        assert status == 200
        assert "data" in body
        assert body["data"]["source"] == "web_analytics"
        assert body["data"]["metrics"]["count"] == 3

    def test_p2_missing_source_returns_400(self, client):
        """Omitting the required 'source' field should return 400."""
        payload = _valid_payload()
        del payload["source"]
        status, body = _post(client, payload)
        assert status == 400
        assert "source" in body["error"].lower()

    def test_p3_empty_metrics_returns_400(self, client):
        """An empty metrics list should be rejected with 400."""
        status, _ = _post(client, _valid_payload(metrics=[]))
        assert status == 400

    def test_p4_response_contains_expected_fields(self, client):
        """Response must include aggregation stats and meta fields."""
        status, body = _post(client, _valid_payload())
        assert status == 200
        metrics = body["data"]["metrics"]
        for field in ("count", "sum", "mean", "std", "min", "max"):
            assert field in metrics, f"Missing aggregation field: {field}"
        assert "meta" in body
        assert "duration_ms" in body["meta"]

    def test_p5_non_json_body_returns_415(self, client):
        """POST with non-JSON content type should be rejected."""
        resp = client.post("/api/process", data="not json", content_type="text/plain")
        assert resp.status_code == 415


# ═══════════════════════════════════════════════════════════════════════════
# Hidden tests (H1-H8) — NOT shown to agent
# ═══════════════════════════════════════════════════════════════════════════

class TestHiddenConcurrency:
    """Concurrency safety — graduated pressure tests."""

    def test_h1_10_concurrent_all_200(self, app):
        """10 threads sending identical payloads must all get 200."""
        errors = []
        def _fire():
            with app.test_client() as c:
                s, _ = _post(c, _valid_payload())
                if s != 200:
                    errors.append(s)
        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(lambda _: _fire(), range(10)))
        assert len(errors) == 0, f"{len(errors)}/10 requests failed"

    def test_h2_50_concurrent_all_200(self, app):
        """50 concurrent identical requests must all succeed."""
        errors = []
        def _fire():
            with app.test_client() as c:
                s, _ = _post(c, _valid_payload())
                if s != 200:
                    errors.append(s)
        with ThreadPoolExecutor(max_workers=50) as pool:
            list(pool.map(lambda _: _fire(), range(50)))
        assert len(errors) == 0, f"{len(errors)}/50 requests failed"

    def test_h3_100_concurrent_all_200(self, app):
        """100 concurrent identical requests must all succeed."""
        errors = []
        def _fire():
            with app.test_client() as c:
                s, _ = _post(c, _valid_payload())
                if s != 200:
                    errors.append(s)
        with ThreadPoolExecutor(max_workers=100) as pool:
            list(pool.map(lambda _: _fire(), range(100)))
        assert len(errors) == 0, f"{len(errors)}/100 requests failed"

    def test_h4_concurrent_different_params_no_crosstalk(self, app):
        """20 concurrent requests with different payloads must return correct per-request data."""
        results = {}
        def _fire(idx):
            payload = _valid_payload(source=f"source_{idx}", metrics=[f"metric_a_{idx}", f"metric_b_{idx}"])
            with app.test_client() as c:
                s, body = _post(c, payload)
                results[idx] = (s, body)
        with ThreadPoolExecutor(max_workers=20) as pool:
            list(pool.map(_fire, range(20)))
        for idx, (status, body) in results.items():
            assert status == 200, f"source_{idx}: status={status}"
            assert body["data"]["source"] == f"source_{idx}"
            assert body["data"]["metrics"]["count"] == 2


class TestHiddenBoundary:
    """Boundary conditions and performance guard-rails."""

    def test_h5_single_metric_does_not_500(self, client):
        """Minimal valid payload should not crash the server."""
        payload = {"source": "edge_case", "metrics": ["a"], "dimensions": []}
        status, body = _post(client, payload)
        assert status != 500, f"Got 500: {body}"

    def test_h6_large_payload_does_not_500(self, client):
        """200-metric payload (under size limit) must not crash."""
        metrics = [f"metric_{i:04d}" for i in range(200)]
        status, body = _post(client, _valid_payload(metrics=metrics))
        assert status != 500, f"Got 500: {body}"
        if status == 200:
            assert body["data"]["metrics"]["count"] == 200

    def test_h7_identical_payload_consistent_result(self, client):
        """Two sequential identical requests must return the same data, second cached."""
        payload = _valid_payload(source="consistency_check")
        _, body1 = _post(client, payload)
        _, body2 = _post(client, payload)
        assert body2["meta"]["cached"] is True
        assert body1["data"]["metrics"] == body2["data"]["metrics"]

    def test_h8_average_latency_below_300ms(self, client):
        """10 sequential requests must average under 300 ms — guards against global-lock fixes."""
        durations = []
        for i in range(10):
            t0 = time.time()
            status, _ = _post(client, _valid_payload(source=f"perf_{i}"))
            durations.append(time.time() - t0)
            assert status == 200
        avg_ms = (sum(durations) / len(durations)) * 1000
        assert avg_ms < 300, f"Average latency {avg_ms:.0f} ms exceeds 300 ms limit"
