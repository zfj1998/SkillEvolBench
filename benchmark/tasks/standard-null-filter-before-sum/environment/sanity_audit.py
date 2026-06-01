from __future__ import annotations


def build_sanity_checks(summary: dict) -> dict:
    total_rows = int(summary["total_rows"])
    valid_count = int(summary["valid_amount_count"])
    missing_count = int(summary["missing_amount_count"])
    average_amount = float(summary["average_amount"])
    denominator_used = int(summary.get("denominator_used", total_rows))
    return {
        "non_empty_valid_values": valid_count > 0,
        "count_consistent": valid_count + missing_count == total_rows and valid_count == total_rows,
        "denominator_matches_valid_rows": denominator_used == valid_count,
        "average_in_expected_band": 90.0 <= average_amount <= 110.0,
    }
