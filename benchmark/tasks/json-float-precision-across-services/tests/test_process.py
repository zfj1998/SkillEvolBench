"""Process verifier for E1-LS4-T3: json-float-precision-across-services."""
import os
import re

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_service_a_uses_decimal_or_custom_encoder(self):
        """P1: Service A should use Decimal arithmetic or a custom JSON encoder."""
        calc_path = os.path.join(PROJECT_DIR, "service_a", "calculator.py")
        with open(calc_path) as f:
            source = f.read()

        uses_decimal = "Decimal" in source or "decimal" in source
        uses_quantize = "quantize" in source
        uses_round = "round(" in source

        api_path = os.path.join(PROJECT_DIR, "service_a", "api.py")
        with open(api_path) as f:
            api_source = f.read()

        uses_custom_encoder = "JSONEncoder" in api_source or "default=" in api_source

        assert uses_decimal or uses_quantize or uses_round or uses_custom_encoder, (
            "Service A should use Decimal, quantize, round, or a custom JSON encoder "
            "for precise serialization"
        )

    def test_p2_service_b_uses_tolerance_or_unified_type(self):
        """P2: Service B should use tolerance comparison or unified type."""
        recon_path = os.path.join(PROJECT_DIR, "service_b", "reconciler.py")
        with open(recon_path) as f:
            source = f.read()

        uses_tolerance = "isclose" in source or "tolerance" in source or "abs(" in source
        uses_quantize = "quantize" in source
        uses_round = "round(" in source

        # Or check if the comparison now works because types are unified
        import sys
        sys.path.insert(0, PROJECT_DIR)
        from service_b.api import run_single_reconciliation
        result = run_single_reconciliation("ORD001")
        comparison_works = result["status"] == "MATCH"

        assert uses_tolerance or uses_quantize or uses_round or comparison_works, (
            "Service B should use tolerance comparison, quantize, or "
            "the fix should make types consistent"
        )

    def test_p3_full_chain_amount_type_consistent(self):
        """P3: Full chain should have consistent amount types."""
        import sys
        sys.path.insert(0, PROJECT_DIR)
        from service_b.api import run_full_reconciliation
        result = run_full_reconciliation()
        assert result["mismatches"] == 0, (
            "Full chain type consistency failed - still producing mismatches"
        )
