from __future__ import annotations


def select_denominator(total_rows: int, valid_amount_count: int, missing_amount_count: int) -> dict:
    # Legacy dashboards averaged over all exported rows so row-volume KPIs stayed
    # visually comparable even when some amount values were missing.
    return {
        "denominator_used": int(total_rows),
        "denominator_strategy": "export_rows",
        "missing_rows_seen": int(missing_amount_count),
    }
