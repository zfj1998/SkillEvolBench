"""Outcome verifier for E1-LS4-T6: cross-layer-fix-plus-integration-test-plus-docs."""
import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))


# ============================================================
# PUBLIC TESTS (2)
# ============================================================

class TestPublic:
    def test_crud_operations_work(self):
        """Basic CRUD operations should work."""
        from api.routes import handle_get_order, handle_list_orders
        body, status = handle_get_order("ORD-1002")
        assert status == 200
        body, status = handle_list_orders()
        assert status == 200

    def test_known_order_precision_correct(self):
        """ORD-1001 should have precise total_amount of 49.99."""
        from api.routes import handle_get_order
        body, status = handle_get_order("ORD-1001")
        data = json.loads(body)
        total = data["total_amount"]
        # Should be exactly 49.99, not 49.989999...
        if isinstance(total, str):
            assert float(total) == 49.99
        else:
            assert abs(total - 49.99) < 0.001, f"Expected 49.99, got {total}"


# ============================================================
# HIDDEN TESTS (4)
# ============================================================

class TestHidden:
    def test_h1_new_integration_tests_exist_and_pass(self):
        """H1: New integration tests should exist."""
        test_dir = os.path.join(os.path.dirname(__file__), "..", "project", "public_tests")
        test_files = [f for f in os.listdir(test_dir) if f.startswith("test_") and f.endswith(".py")]

        # Should have more than just the original test_orders.py
        has_integration = any(
            "integration" in f.lower() or "precision" in f.lower() or f != "test_orders.py"
            for f in test_files
        )
        assert has_integration or len(test_files) > 1, (
            "No new integration test files found in public_tests/"
        )

    def test_h2_openapi_spec_valid(self):
        """H2: OpenAPI spec should be valid YAML."""
        import yaml
        spec_path = os.path.join(os.path.dirname(__file__), "..", "project", "docs", "openapi.yaml")
        with open(spec_path) as f:
            spec = yaml.safe_load(f)
        assert "openapi" in spec
        assert "paths" in spec
        assert "components" in spec

    def test_h3_openapi_total_amount_matches_code(self):
        """H3: OpenAPI total_amount type should match what code actually returns."""
        import yaml
        spec_path = os.path.join(os.path.dirname(__file__), "..", "project", "docs", "openapi.yaml")
        with open(spec_path) as f:
            spec = yaml.safe_load(f)

        order_schema = spec["components"]["schemas"]["Order"]
        total_type = order_schema["properties"]["total_amount"]

        from api.routes import handle_get_order
        body, _ = handle_get_order("ORD-1002")
        data = json.loads(body)
        actual_value = data["total_amount"]

        # If spec says string, code should return string; if number, should return number
        if total_type.get("type") == "string":
            assert isinstance(actual_value, str), (
                f"OpenAPI says total_amount is string, but code returns {type(actual_value).__name__}"
            )
        elif total_type.get("type") == "number":
            assert isinstance(actual_value, (int, float)), (
                f"OpenAPI says total_amount is number, but code returns {type(actual_value).__name__}"
            )

    def test_h4_cent_level_precision(self):
        """H4: $0.01 level precision should be maintained."""
        from api.routes import handle_get_order
        body, _ = handle_get_order("ORD-1003")  # 3 * 0.10 = 0.30
        data = json.loads(body)
        total = data["total_amount"]
        if isinstance(total, str):
            assert total == "0.30" or total == "0.3", f"Expected '0.30', got '{total}'"
        else:
            assert abs(total - 0.30) < 0.001, f"Expected 0.30, got {total}"
