from __future__ import annotations


def build_reconciliation(source_total: float, grouped_total: float) -> dict:
    return {
        "source_total": round(float(source_total), 2),
        "grouped_total": round(float(grouped_total), 2),
        "matches_source_total": round(float(source_total), 2) == round(float(grouped_total), 2),
    }
