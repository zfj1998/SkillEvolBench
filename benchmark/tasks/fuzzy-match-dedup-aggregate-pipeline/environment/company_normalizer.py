from __future__ import annotations

import re


def canonical_company(value: str) -> str:
    normalized = str(value).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def revenue_segment(annual_revenue: float) -> str:
    if annual_revenue >= 3_500_000:
        return "enterprise"
    if annual_revenue >= 1_500_000:
        return "mid_market"
    return "growth"
