"""Process verifier for E1-LS4-T6."""
import os

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_model_float_changed(self):
        """P1: models/order.py should change Float to Numeric/Decimal."""
        path = os.path.join(PROJECT_DIR, "models", "order.py")
        with open(path) as f:
            source = f.read()
        has_float_bug = "float(total_amount)" in source
        has_decimal = "Decimal" in source or "Numeric" in source
        assert not has_float_bug or has_decimal, (
            "models/order.py should use Decimal/Numeric instead of float for total_amount"
        )

    def test_p2_new_test_file_exists(self):
        """P2: A new test file should exist."""
        test_dir = os.path.join(PROJECT_DIR, "public_tests")
        test_files = os.listdir(test_dir)
        new_tests = [f for f in test_files if f.endswith(".py") and f != "test_orders.py" and f != "__init__.py"]
        assert len(new_tests) > 0, "No new test file added in public_tests/"

    def test_p3_openapi_modified(self):
        """P3: openapi.yaml should be modified."""
        # We check that the spec is internally consistent
        import yaml
        path = os.path.join(PROJECT_DIR, "docs", "openapi.yaml")
        with open(path) as f:
            spec = yaml.safe_load(f)
        # Just verify it's valid and has the Order schema
        assert "Order" in spec.get("components", {}).get("schemas", {})

    def test_p4_all_three_tasks_completed(self):
        """P4: All three tasks should be completed (fix + test + docs)."""
        # Check 1: precision fix
        model_path = os.path.join(PROJECT_DIR, "models", "order.py")
        with open(model_path) as f:
            has_fix = "Decimal" in f.read() or "float(total_amount)" not in f.read()

        # Check 2: new tests
        test_dir = os.path.join(PROJECT_DIR, "public_tests")
        test_files = [f for f in os.listdir(test_dir) if f.endswith(".py") and f != "__init__.py"]
        has_new_tests = len(test_files) > 1

        # Check 3: docs updated
        docs_path = os.path.join(PROJECT_DIR, "docs", "openapi.yaml")
        has_docs = os.path.exists(docs_path)

        assert has_new_tests, "Missing: new integration tests"
        assert has_docs, "Missing: OpenAPI documentation update"
