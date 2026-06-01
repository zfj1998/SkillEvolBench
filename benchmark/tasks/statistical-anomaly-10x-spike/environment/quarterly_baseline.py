from __future__ import annotations

from statistics import median


def baseline_revenue(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def is_revenue_anomalous(revenue: float, baseline: float) -> bool:
    if baseline <= 0:
        return False
    return revenue > baseline * 8
