"""
Compatibility helpers for the legacy billing bridge.

The old invoice pipeline still sends numeric region codes and sometimes drops
the UI-selected region field entirely. The bridge normalizes those inputs
before the tax lookup layer runs.
"""

from __future__ import annotations

from typing import Dict, Iterable, Tuple


LEGACY_EMPTY_REGION = ""


def normalize_bridge_region(region: str | None) -> str:
    if region is None:
        return LEGACY_EMPTY_REGION
    normalized = str(region).strip().upper()
    return normalized or LEGACY_EMPTY_REGION


def build_rate_vector(rate_map: Dict[str, float]) -> list[float]:
    """
    Preserve the historical insertion-order vector expected by the billing
    bridge. tax_rates.py combines this with an alphabetical code lookup.
    """
    return list(rate_map.values())
