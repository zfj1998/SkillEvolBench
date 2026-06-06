"""Outcome verifier for E1-LS4-T3: json-float-precision-across-services."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))


# ============================================================
# PUBLIC TESTS (2)
# ============================================================

class TestPublic:
    def test_integer_amount_reconciliation_succeeds(self):
        """Simple integer amount should reconcile correctly."""
        from service_b.api import run_single_reconciliation
        result = run_single_reconciliation("ORD002")  # 100.00
        assert result["status"] == "MATCH"

    def test_known_change_correctly_flagged(self):
        """An order with a genuinely different amount should MISMATCH."""
        from service_b.reconciler import reconcile_order
        import json
        # Simulate an API response with a different total
        fake_api = json.dumps({
            "id": "ORD002", "item": "Widget B",
            "quantity": 1, "unit_price": 100.0, "calculated_total": 150.0
        })
        result = reconcile_order(fake_api)
        assert result["status"] == "MISMATCH"


# ============================================================
# HIDDEN TESTS (4)
# ============================================================

class TestHidden:
    def test_h1_precision_0_1_times_3(self):
        """H1: 0.1 * 3 should reconcile as MATCH (not precision mismatch)."""
        from service_b.api import run_single_reconciliation
        result = run_single_reconciliation("ORD001")  # 3 * 0.10 = 0.30
        assert result["status"] == "MATCH", (
            f"ORD001 (0.1*3) should be MATCH but got {result['status']}. "
            f"Details: {result.get('api_total')} vs {result.get('db_total')}"
        )

    def test_h2_large_amount_reconciliation(self):
        """H2: $999,999.99 should reconcile correctly."""
        from service_b.api import run_single_reconciliation
        result = run_single_reconciliation("ORD004")
        assert result["status"] == "MATCH", (
            f"ORD004 ($999,999.99) should be MATCH but got {result['status']}"
        )

    def test_h3_batch_reconciliation_no_false_mismatch(self):
        """H3: Full reconciliation should have 0 false mismatches."""
        from service_b.api import run_full_reconciliation
        result = run_full_reconciliation()
        assert result["mismatches"] == 0, (
            f"Expected 0 mismatches, got {result['mismatches']}. "
            f"Details: {result.get('mismatch_details')}"
        )

    def test_h4_real_change_still_detected(self):
        """H4: A genuinely changed amount should still MISMATCH."""
        from service_b.reconciler import reconcile_order
        import json
        fake_api = json.dumps({
            "id": "ORD001", "item": "Widget A",
            "quantity": 3, "unit_price": 0.20, "calculated_total": 0.60
        })
        result = reconcile_order(fake_api)
        assert result["status"] == "MISMATCH"
