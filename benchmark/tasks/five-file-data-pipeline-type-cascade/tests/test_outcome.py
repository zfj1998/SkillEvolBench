"""Outcome verifier for E1-LS4-T1: five-file-data-pipeline-type-cascade."""
import sys
import os
import pytest
from decimal import Decimal

# Add fixture to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))


# ============================================================
# PUBLIC TESTS (3)
# ============================================================

class TestPublic:
    def test_single_unchanged_record_not_marked(self):
        """A single record with unchanged amount should not be flagged."""
        from enricher import enrich_record
        record = {"id": 1, "amount": Decimal("100.50")}
        result = enrich_record(record)
        assert result["changed"] is False, "Unchanged record should not be marked as changed"

    def test_real_change_detected(self):
        """A genuinely changed record should be flagged."""
        from enricher import enrich_record
        record = {"id": 1, "amount": Decimal("200.00")}  # Was 100.50
        result = enrich_record(record)
        assert result["changed"] is True, "Changed record should be marked as changed"

    def test_pipeline_runs_without_error(self):
        """The full pipeline should execute without errors."""
        from pipeline import run_pipeline
        result = run_pipeline()
        assert result is not None
        assert "total" in result
        assert result["total"] == 5


# ============================================================
# HIDDEN TESTS (5)
# ============================================================

class TestHidden:
    def test_h1_batch_500_no_false_positives(self):
        """H1: 500 unchanged records should produce 0 false positives."""
        from extractor import HISTORICAL_DB
        from enricher import enrich_record

        false_positives = 0
        for i in range(500):
            record_id = (i % 5) + 1
            amount = HISTORICAL_DB[record_id]  # Same as historical
            result = enrich_record({"id": record_id, "amount": amount})
            if result["changed"]:
                false_positives += 1

        assert false_positives == 0, f"Expected 0 false positives, got {false_positives}"

    def test_h2_precision_0_1_plus_0_2(self):
        """H2: 0.1 + 0.2 precision - enricher should judge as unchanged."""
        from enricher import enrich_record
        # Record 2 has amount Decimal("0.30") in historical
        # After correct fix, Decimal("0.30") == Decimal("0.30") -> not changed
        record = {"id": 2, "amount": Decimal("0.30")}
        result = enrich_record(record)
        assert result["changed"] is False, (
            "Decimal('0.30') should match historical Decimal('0.30') - "
            "precision issue detected"
        )

    def test_h3_decimal_type_preserved_in_pipeline(self):
        """H3: Decimal type should be preserved through the pipeline."""
        from pipeline import run_pipeline
        from decimal import Decimal

        result = run_pipeline()
        # Check that amounts in records are still Decimal (not float)
        all_records = result["changed_records"] + result["unchanged_records"]
        for record in all_records:
            assert isinstance(record["amount"], Decimal), (
                f"Record {record['id']}: amount is {type(record['amount']).__name__}, "
                f"expected Decimal"
            )

    def test_h4_genuine_change_still_detected(self):
        """H4: A real change (100 -> 200) should still be correctly flagged."""
        from enricher import enrich_record
        record = {"id": 1, "amount": Decimal("200.00")}  # Historical is 100.50
        result = enrich_record(record)
        assert result["changed"] is True

    def test_h5_large_amount_comparison_correct(self):
        """H5: Large amounts ($999,999.99) should compare correctly."""
        from enricher import enrich_record
        record = {"id": 3, "amount": Decimal("999999.99")}
        result = enrich_record(record)
        assert result["changed"] is False, "Large unchanged amount should not be flagged"
