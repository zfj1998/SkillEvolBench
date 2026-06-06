"""Process verifier for E1-LS4-T1: five-file-data-pipeline-type-cascade."""
import os
import re
import ast


PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_float_conversion_removed_from_validator(self):
        """P1: validator.py should no longer convert amounts to float."""
        validator_path = os.path.join(PROJECT_DIR, "validator.py")
        with open(validator_path) as f:
            source = f.read()

        # Check that float() conversion on amount is removed
        # Look for patterns like: float(record["amount"]) or float(record['amount'])
        float_patterns = [
            r'float\s*\(\s*record\s*\[\s*["\']amount["\']\s*\]\s*\)',
            r'record\s*\[\s*["\']amount["\']\s*\]\s*=\s*float\s*\(',
        ]
        for pattern in float_patterns:
            assert not re.search(pattern, source), (
                f"validator.py still contains float() conversion on amount: "
                f"pattern '{pattern}' found"
            )

    def test_p2_pipeline_preserves_decimal_type(self):
        """P2: Pipeline should maintain Decimal type throughout."""
        import sys
        sys.path.insert(0, PROJECT_DIR)
        from decimal import Decimal
        from extractor import extract_records
        from validator import validate_batch

        records = extract_records()
        validated = validate_batch(records)
        for record in validated:
            assert isinstance(record["amount"], Decimal), (
                f"After validation, record {record['id']} amount is "
                f"{type(record['amount']).__name__}, expected Decimal"
            )

    def test_p3_enricher_uses_type_safe_comparison(self):
        """P3: Enricher comparison should be type-safe (Decimal to Decimal or math.isclose)."""
        import sys
        sys.path.insert(0, PROJECT_DIR)
        from decimal import Decimal
        from enricher import enrich_record

        # Test with Decimal - should work correctly
        record = {"id": 2, "amount": Decimal("0.30")}
        result = enrich_record(record)
        assert result["changed"] is False, (
            "Enricher comparison is not type-safe: Decimal('0.30') vs "
            "historical Decimal('0.30') should be equal"
        )
